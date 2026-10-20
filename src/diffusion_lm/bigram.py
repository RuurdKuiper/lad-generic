"""Sparse count bigrams and exact O(B K²) Viterbi token selection.

Candidate-only scores are relative emissions (no full-vocabulary normalization
can be recovered). Use ``select_block`` when full diffusion logits are available.
No transitions are inserted across document boundaries during count building.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable

import torch


def tokenizer_fingerprint(tokenizer) -> str:
    """Fingerprint the token-to-ID mapping, including special tokens."""
    payload = json.dumps(sorted(tokenizer.get_vocab().items()), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


class BigramScorer(torch.nn.Module):
    """P(next|prev) = (count(prev,next) + alpha * unigram(next)) / (count(prev) + alpha).

    Unigrams have additive beta smoothing, so unseen/special tokens remain
    finite. Storage is O(observed pairs + vocabulary), never vocabulary squared.
    Pair keys are sorted int64 values for vectorized searchsorted lookups.
    """

    def __init__(self, vocab_size, pair_keys, pair_counts, unigram_counts, *, alpha=10.0,
                 beta=0.1, metadata=None, successor_counts=None):
        super().__init__()
        if int(vocab_size) < 1 or not math.isfinite(alpha) or alpha <= 0 or not math.isfinite(beta) or beta <= 0:
            raise ValueError("vocab_size, alpha, and beta must be positive and finite")
        self.vocab_size = int(vocab_size)
        self.alpha, self.beta = float(alpha), float(beta)
        self.metadata = metadata or {}
        keys = torch.as_tensor(pair_keys, dtype=torch.long)
        counts = torch.as_tensor(pair_counts, dtype=torch.float32)
        unigrams = torch.as_tensor(unigram_counts, dtype=torch.float32)
        if keys.ndim != 1 or counts.shape != keys.shape or unigrams.shape != (self.vocab_size,):
            raise ValueError("Invalid sparse bigram checkpoint shapes")
        if (keys < 0).any() or (keys >= self.vocab_size**2).any() or (keys[1:] <= keys[:-1]).any():
            raise ValueError("Pair keys must be sorted, unique, and within the vocabulary")
        if not torch.isfinite(counts).all() or not torch.isfinite(unigrams).all() or (counts < 0).any() or (unigrams < 0).any():
            raise ValueError("Counts must be finite and nonnegative")
        totals = torch.zeros(self.vocab_size)
        totals.scatter_add_(0, keys // self.vocab_size, counts)
        successors = torch.zeros(self.vocab_size)
        successors.scatter_add_(0, keys % self.vocab_size, counts)
        if successor_counts is not None:
            saved_successors = torch.as_tensor(successor_counts, dtype=torch.float32)
            if saved_successors.shape != successors.shape or not torch.equal(saved_successors, successors):
                raise ValueError("Successor counts do not match sparse bigram counts")
        self.register_buffer("successor_counts", successors)
        self.register_buffer("successor_unigram", (successors + beta) / (successors.sum() + beta * self.vocab_size))
        self.register_buffer("pair_keys", keys)
        self.register_buffer("pair_counts", counts)
        self.register_buffer("row_totals", totals)
        self.register_buffer("unigram_counts", unigrams)
        self.register_buffer("unigram", (unigrams + beta) / (unigrams.sum() + beta * self.vocab_size))

    @classmethod
    def from_sequences(cls, sequences: Iterable[Iterable[int]], vocab_size: int, **kwargs):
        pairs, unigrams = Counter(), Counter()
        for sequence in sequences:
            ids = [int(i) for i in sequence]
            if any(i < 0 or i >= vocab_size for i in ids):
                raise ValueError("Training token outside tokenizer vocabulary")
            unigrams.update(ids)
            pairs.update(a * vocab_size + b for a, b in zip(ids, ids[1:]))
        keys = sorted(pairs)
        return cls(vocab_size, keys, [pairs[k] for k in keys],
                   [unigrams[i] for i in range(vocab_size)], **kwargs)

    def _lookup_counts(self, previous: torch.Tensor, following: torch.Tensor) -> torch.Tensor:
        if previous.device != self.pair_keys.device or following.device != self.pair_keys.device:
            raise ValueError("Move the bigram scorer to the candidate device before scoring")
        # Checkpoints cover the backbone vocabulary. Out-of-range IDs are errors,
        # rather than aliases for unrelated pairs through packed-key overflow.
        if ((previous < 0) | (previous >= self.vocab_size)).any() or ((following < 0) | (following >= self.vocab_size)).any():
            raise ValueError("Candidate token outside bigram vocabulary")
        query = previous * self.vocab_size + following
        if self.pair_keys.numel():
            index = torch.searchsorted(self.pair_keys, query.contiguous())
            safe = index.clamp_max(self.pair_keys.numel() - 1)
            counts = torch.where((index < self.pair_keys.numel()) & (self.pair_keys[safe] == query),
                                 self.pair_counts[safe], 0.0)
        else:
            counts = torch.zeros_like(query, dtype=torch.float32)
        return counts

    def _conditional(self, counts, previous, following):
        # Keep the original all-token unigram backoff for conditional compatibility.
        return (counts + self.alpha * self.unigram[following]).log() - (self.row_totals[previous] + self.alpha).log()

    def log_prob(self, previous: torch.Tensor, following: torch.Tensor) -> torch.Tensor:
        """Original smoothed conditional probability, independent of scoring mode."""
        return self._conditional(self._lookup_counts(previous, following), previous, following)

    @staticmethod
    def validate_scoring(scoring_method, min_count, pmi_clip):
        if scoring_method not in {"conditional", "pmi"}:
            raise ValueError("Scoring method must be 'conditional' or 'pmi'")
        if not isinstance(min_count, int) or isinstance(min_count, bool) or min_count < 0:
            raise ValueError("PMI minimum count must be a nonnegative integer")
        if not math.isfinite(pmi_clip) or pmi_clip < 0:
            raise ValueError("PMI clipping bound must be finite and nonnegative")

    def transition_score(self, previous, following, *, scoring_method="conditional", min_count=5, pmi_clip=5.0):
        """Conditional log-probability or guarded PMI using successor marginals.

        Unseen pairs always score zero in PMI mode, including min_count=0.
        Only the PMI correction is clipped; diffusion emissions are untouched.
        """
        self.validate_scoring(scoring_method, min_count, pmi_clip)
        counts = self._lookup_counts(previous, following)
        conditional = self._conditional(counts, previous, following)
        if scoring_method == "conditional":
            return conditional
        pmi = conditional - self.successor_unigram[following].log()
        return torch.where((counts > 0) & (counts >= min_count), pmi.clamp(-pmi_clip, pmi_clip), 0.0)

    def forward(self, token_ids: torch.Tensor, logits: torch.Tensor, *, scoring_method="conditional", min_count=5, pmi_clip=5.0) -> torch.Tensor:
        """Return all adjacent transition scores [B-1,K,K] in one tensor operation."""
        if token_ids.ndim != 2 or logits.shape != token_ids.shape:
            raise ValueError("Expected token_ids and logits [B,K]")
        return self.transition_score(token_ids[:-1, :, None], token_ids[1:, None, :],
                                     scoring_method=scoring_method, min_count=min_count, pmi_clip=pmi_clip)

    def save(self, path: str | Path):
        torch.save(dict(version=2, vocab_size=self.vocab_size, pair_keys=self.pair_keys.cpu(),
                        pair_counts=self.pair_counts.cpu(), unigram_counts=self.unigram_counts.cpu(),
                        successor_counts=self.successor_counts.cpu(),
                        alpha=self.alpha, beta=self.beta, metadata=self.metadata), path)

    @classmethod
    def load(cls, path: str | Path, *, tokenizer=None, device="cpu"):
        if not Path(path).is_file():
            raise FileNotFoundError(f"Bigram checkpoint unavailable: {path}. Build it with scripts/build_bigram.py.")
        state = torch.load(path, map_location="cpu", weights_only=True)
        if state.pop("version", None) not in {1, 2}:
            raise ValueError("Unsupported bigram checkpoint version")
        scorer = cls(**state)
        if tokenizer is not None and scorer.metadata.get("tokenizer_sha256") != tokenizer_fingerprint(tokenizer):
            raise ValueError("Bigram checkpoint tokenizer does not match the inference tokenizer")
        return scorer.to(device)


class BigramViterbiSelector:
    def __init__(self, scorer, weight=0.5, *, scoring_method="conditional", min_count=5, pmi_clip=5.0, remasking_confidence="diffusion"):
        if not math.isfinite(weight) or weight < 0:
            raise ValueError("Bigram weight must be finite and nonnegative")
        BigramScorer.validate_scoring(scoring_method, min_count, pmi_clip)
        if remasking_confidence not in {"diffusion", "viterbi_margin"}:
            raise ValueError("Remasking confidence must be 'diffusion' or 'viterbi_margin'")
        self.remasking_confidence = remasking_confidence
        self.last_path_margins = None
        self.scorer, self.weight = scorer, float(weight)
        self.scoring_method, self.min_count, self.pmi_clip = scoring_method, min_count, float(pmi_clip)

    def _score(self, previous, following):
        return self.scorer.transition_score(previous, following, scoring_method=self.scoring_method,
                                            min_count=self.min_count, pmi_clip=self.pmi_clip)

    @staticmethod
    def decode(token_ids, logits, transitions, weight=0.5):
        """Exact DP; each emission is added once. Only the time axis is sequential."""
        if token_ids.ndim != 2 or token_ids.shape != logits.shape or min(token_ids.shape) < 1:
            raise ValueError("Expected nonempty token_ids and logits [B,K]")
        length, k = token_ids.shape
        if transitions.shape != (length - 1, k, k):
            raise ValueError("Expected transitions [B-1,K,K]")
        if weight == 0 or length == 1:
            return token_ids.gather(1, logits.argmax(-1, keepdim=True)).squeeze(1)
        scores = logits[0].float()
        back = torch.empty((length - 1, k), dtype=torch.long, device=logits.device)
        for t in range(1, length):
            scores, back[t - 1] = (scores[:, None] + weight * transitions[t - 1]).max(dim=0)
            scores = scores + logits[t].float()
        path = torch.empty(length, dtype=torch.long, device=logits.device)
        path[-1] = scores.argmax()
        for t in range(length - 2, -1, -1):
            path[t] = back[t, path[t + 1]]
        return token_ids.gather(1, path[:, None]).squeeze(1)

    def __call__(self, token_ids, logits):
        if self.weight == 0 or token_ids.shape[0] == 1:
            return token_ids.gather(1, logits.argmax(-1, keepdim=True)).squeeze(1)
        transitions = self.scorer(token_ids, logits, scoring_method=self.scoring_method,
                                  min_count=self.min_count, pmi_clip=self.pmi_clip)
        return self.decode(token_ids, logits, transitions, self.weight)

    @staticmethod
    def path_margins(token_ids, emissions, transitions, selected_ids, weight=0.5):
        """Best complete path through selected ID minus best through another ID.

        Forward/backward max-sum passes cost O(B K²), without enumerating paths.
        Centering each DP row removes shared constants for numerical stability.
        Fixed rows and K=1 have infinite margins (no alternative in the lattice).
        These are score gaps, not probabilities or full-vocabulary uncertainty.
        """
        length, k = emissions.shape
        if token_ids.shape != emissions.shape or selected_ids.shape != (length,):
            raise ValueError("Expected candidates/emissions [B,K] and selected IDs [B]")
        if length < 1 or k < 1 or transitions.shape != (length - 1, k, k):
            raise ValueError("Expected nonempty lattice and transitions [B-1,K,K]")
        unary = emissions.float() - emissions.float().max(-1, keepdim=True).values
        edges = transitions.float() * weight if weight else torch.zeros_like(transitions, dtype=torch.float32)
        forward = torch.empty_like(unary)
        backward = torch.empty_like(unary)
        forward[0] = unary[0]
        for t in range(1, length):
            row = unary[t] + (forward[t - 1, :, None] + edges[t - 1]).max(0).values
            forward[t] = row - row.max()
        backward[-1] = 0.
        for t in range(length - 2, -1, -1):
            row = (edges[t] + unary[t + 1, None, :] + backward[t + 1, None, :]).max(1).values
            backward[t] = row - row.max()
        scores = forward + backward
        same_id = token_ids == selected_ids[:, None]
        best_selected = scores.masked_fill(~same_id, -torch.inf).max(-1).values
        best_alternative = scores.masked_fill(same_id, -torch.inf).max(-1).values
        return (best_selected - best_alternative).clamp_min(0.)

    def select_block(self, logits, current_ids, editable, *, top_k=16, temperature=1.0, left_id=None, right_id=None):
        """Decode a contiguous block; fixed rows and external neighbors constrain it.

        Full-vocabulary log_softmax precedes top-k extraction. Fixed rows have
        one possible ID and zero emission (a path-independent constant).
        Boundary context adds transition terms without extra emission terms.
        Temperature scales emissions relative to bigrams. For T > 0, maximizing
        log_softmax(logits / T) + weight * transitions is equivalent to using
        raw log probabilities + (weight * T) * transitions. The latter avoids
        division by tiny T and has the exact greedy limit at T=0. Margins use
        these common rescaled units, preserving their retention ranking.
        Returned diffusion confidence always uses raw full-vocabulary p_t.
        """
        if logits.ndim != 2 or current_ids.shape != logits.shape[:1] or editable.shape != current_ids.shape:
            raise ValueError("Expected logits [B,V], current_ids/editable [B]")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        temperature = float(temperature)
        if not math.isfinite(temperature) or temperature < 0:
            raise ValueError("temperature must be finite and nonnegative")
        weight = self.weight * temperature
        if not math.isfinite(weight):
            raise ValueError("temperature times bigram weight must be finite")
        self.last_path_margins = None
        log_probs = logits.float().log_softmax(-1)
        if weight == 0 and self.remasking_confidence == "diffusion":
            # topk need not break tied maxima like argmax (common for BF16).
            # The zero-weight baseline must exactly match full-vocabulary argmax.
            selected = torch.where(editable, logits.argmax(-1), current_ids)
            return selected, log_probs.gather(1, selected[:, None]).squeeze(1).exp()
        emissions, candidates = log_probs.topk(min(int(top_k), logits.shape[-1]), dim=-1)
        if weight == 0 or top_k == 1:
            # Keep full-vocabulary argmax tie behavior even if topk omits that
            # tied ID. Replacing one tied maximum leaves a valid top-k lattice.
            argmax_ids = logits.argmax(-1)
            absent = ~(candidates == argmax_ids[:, None]).any(-1)
            candidates[absent, 0] = argmax_ids[absent]
            emissions[absent, 0] = log_probs.gather(1, argmax_ids[:, None]).squeeze(1)[absent]
        candidates = torch.where(editable[:, None], candidates, current_ids[:, None])
        fixed_scores = torch.full_like(emissions, -torch.inf)
        fixed_scores[:, 0] = 0.0
        emissions = torch.where(editable[:, None], emissions, fixed_scores)
        if weight:
            if left_id is not None:
                left = torch.as_tensor(left_id, device=logits.device, dtype=torch.long)
                emissions[0] += weight * self._score(left, candidates[0])
            if right_id is not None:
                right = torch.as_tensor(right_id, device=logits.device, dtype=torch.long)
                emissions[-1] += weight * self._score(candidates[-1], right)
        if self.remasking_confidence == "viterbi_margin":
            transitions = (
                self.scorer(candidates, emissions, scoring_method=self.scoring_method,
                            min_count=self.min_count, pmi_clip=self.pmi_clip)
                if weight else emissions.new_zeros((len(emissions) - 1, emissions.shape[1], emissions.shape[1]))
            )
            selected = (
                self.decode(candidates, emissions, transitions, weight)
                if weight else torch.where(editable, logits.argmax(-1), current_ids)
            )
            self.last_path_margins = self.path_margins(candidates, emissions, transitions, selected, weight)
        else:
            transitions = self.scorer(candidates, emissions, scoring_method=self.scoring_method,
                                      min_count=self.min_count, pmi_clip=self.pmi_clip)
            selected = self.decode(candidates, emissions, transitions, weight)
        confidence = log_probs.gather(1, selected[:, None]).squeeze(1).exp()
        return selected, confidence
