"""Sparse, smoothed trigram corrections and exact second-order chain decoding."""
from pathlib import Path
import math

import torch

MAX_TRIGRAM_LOOKUP_ELEMENTS = 2_000_000


class TrigramScorer(torch.nn.Module):
    """Correction log P(c|a,b) - log P(c|b), with bigram backoff.

    All context totals precede singleton filtering during training. Unseen or
    low-count triples give zero correction; clipping limits corpus preferences.
    """
    def __init__(self,vocab_size,triple_keys,triple_counts,prefix_keys,prefix_counts,*,alpha=50.,metadata=None):
        super().__init__()
        if vocab_size<1 or vocab_size**3>=2**63 or not math.isfinite(alpha) or alpha<=0:
            raise ValueError('Invalid trigram vocabulary or smoothing')
        self.vocab_size=int(vocab_size);self.alpha=float(alpha);self.metadata=metadata or {}
        for name,keys,counts,limit in [('triple',triple_keys,triple_counts,vocab_size**3),('prefix',prefix_keys,prefix_counts,vocab_size**2)]:
            keys=torch.as_tensor(keys,dtype=torch.long);counts=torch.as_tensor(counts,dtype=torch.float32)
            if keys.ndim!=1 or counts.shape!=keys.shape or (keys<0).any() or (keys>=limit).any() or (keys[1:]<=keys[:-1]).any():
                raise ValueError('Invalid sorted sparse trigram keys')
            if not torch.isfinite(counts).all() or (counts<=0).any():raise ValueError('Invalid trigram counts')
            self.register_buffer(name+'_keys',keys);self.register_buffer(name+'_counts',counts)

    @staticmethod
    def _lookup(keys,counts,query):
        if not keys.numel():return torch.zeros_like(query,dtype=torch.float32)
        index=torch.searchsorted(keys,query.contiguous());safe=index.clamp_max(len(keys)-1)
        return torch.where((index<len(keys))&(keys[safe]==query),counts[safe],0.)

    def correction(self,a,b,c,bigram,*,min_count=2,clip=2.):
        if bigram.vocab_size!=self.vocab_size:raise ValueError('Bigram/trigram vocabulary mismatch')
        if not isinstance(min_count,int) or min_count<1 or not math.isfinite(clip) or clip<0:
            raise ValueError('Invalid trigram minimum count or clipping')
        if min_count < self.metadata.get('storage_min_count', 1):
            raise ValueError('Requested count threshold is below checkpoint storage threshold')
        a,b,c=torch.broadcast_tensors(a,b,c)
        for ids in (a,b,c):
            if ids.device!=self.triple_keys.device:raise ValueError('Move trigram scorer to candidate device')
            if ((ids<0)|(ids>=self.vocab_size)).any():raise ValueError('Token outside trigram vocabulary')
        context=a*self.vocab_size+b
        counts=self._lookup(self.triple_keys,self.triple_counts,context*self.vocab_size+c)
        totals=self._lookup(self.prefix_keys,self.prefix_counts,context)
        base=bigram.log_prob(b,c)
        smoothed=torch.logaddexp(counts.log(),math.log(self.alpha)+base)-(totals+self.alpha).log()
        return torch.where(counts>=min_count,(smoothed-base).clamp(-clip,clip),0.)

    def lattice_corrections(self,ids,bigram,*,min_count=2,clip=2.):
        k=ids.shape[1]
        if len(ids)<3:return torch.zeros((0,k,k,k),device=ids.device)
        if bigram.vocab_size!=self.vocab_size:raise ValueError('Bigram/trigram vocabulary mismatch')
        if not isinstance(min_count,int) or min_count<1 or not math.isfinite(clip) or clip<0:
            raise ValueError('Invalid trigram minimum count or clipping')
        if min_count<self.metadata.get('storage_min_count',1):
            raise ValueError('Requested count threshold is below checkpoint storage threshold')
        if ids.device!=self.triple_keys.device:raise ValueError('Move trigram scorer to candidate device')
        if ((ids<0)|(ids>=self.vocab_size)).any():raise ValueError('Token outside trigram vocabulary')
        # At ordinary K=16 this is one vectorized lookup across all positions.
        # Large K uses window chunks so sparse-lookup temporaries do not grow
        # into multiple gigabytes beyond the required K^3 potential table.
        chunk=max(1,MAX_TRIGRAM_LOOKUP_ELEMENTS//(k**3))
        output=torch.empty((len(ids)-2,k,k,k),device=ids.device,dtype=torch.float32)
        for start in range(0,len(ids)-2,chunk):
            end=min(len(ids)-2,start+chunk)
            # Prefix totals depend on (a,b), and backoff on (b,c). Looking them
            # up on the full K^3 broadcast repeats each sparse search K times.
            a,b,c=ids[start:end],ids[start+1:end+1],ids[start+2:end+2]
            context=a[:,:,None]*self.vocab_size+b[:,None,:]
            totals=self._lookup(self.prefix_keys,self.prefix_counts,context)[:,:,:,None]
            base=bigram.log_prob(b[:,:,None],c[:,None,:])[:,None,:,:]
            counts=self._lookup(self.triple_keys,self.triple_counts,
                context[:,:,:,None]*self.vocab_size+c[:,None,None,:])
            smoothed=torch.logaddexp(counts.log(),math.log(self.alpha)+base)-(totals+self.alpha).log()
            output[start:end]=torch.where(counts>=min_count,(smoothed-base).clamp(-clip,clip),0.)
        return output

    @classmethod
    def load(cls,path,*,bigram,device='cpu'):
        state=torch.load(Path(path),map_location='cpu',weights_only=True)
        if state.pop('version',None)!=1:raise ValueError('Unsupported trigram checkpoint')
        scorer=cls(**state)
        if scorer.vocab_size!=bigram.vocab_size or scorer.metadata.get('tokenizer_sha256')!=bigram.metadata.get('tokenizer_sha256'):
            raise ValueError('Bigram and trigram tokenizer mismatch')
        if scorer.metadata.get('tokens')!=bigram.metadata.get('tokens'):
            raise ValueError('Bigram and trigram training corpora mismatch')
        return scorer.to(device)


def _potentials(emissions,edges,triples,temperature=1.):
    length,k=emissions.shape
    if edges.shape!=(length-1,k,k) or triples.shape!=(max(0,length-2),k,k,k):
        raise ValueError('Invalid second-order lattice shapes')
    if length<1 or k<1:raise ValueError('Empty second-order lattice')
    temperature=float(temperature)
    if not math.isfinite(temperature) or temperature<=0:raise ValueError('Temperature must be positive')
    scale=max(temperature,1e-6)
    unary=emissions.float();unary=(unary-unary.amax(-1,keepdim=True))/scale
    edges=edges.float();triples=triples.float()
    if edges.numel():edges=(edges-edges.amax((1,2),keepdim=True))/scale
    if triples.numel():triples=(triples-triples.amax((1,2,3),keepdim=True))/scale
    return unary,edges,triples


def _forward(unary,edges,triples,*,maximum=False):
    length,k=unary.shape
    rows=[];back=[]
    if length<2:return rows,back
    row=unary[0,:,None]+unary[1,None,:]+edges[0]
    rows.append(row-row.max())
    for t in range(2,length):
        score=rows[-1][:,:,None]+triples[t-2]
        if maximum:
            row,index=score.max(0);back.append(index)
        else:row=torch.logsumexp(score,0)
        row=row+edges[t-1]+unary[t,None,:]
        rows.append(row-row.max())
    return rows,back


def decode_second_order(ids,emissions,edges,triples):
    unary,edges,triples=_potentials(emissions,edges,triples)
    if len(ids)==1:return ids.gather(1,unary.argmax(-1,keepdim=True)).squeeze(1)
    forward,back=_forward(unary,edges,triples,maximum=True)
    k=ids.shape[1]
    if ids.device.type!='cuda':
        # Scalar indexing is inexpensive on CPU; retain its lean traceback.
        path=torch.empty(len(ids),device=ids.device,dtype=torch.long)
        last=forward[-1].reshape(-1).argmax();path[-2]=last//k;path[-1]=last%k
        for t in range(len(ids)-3,-1,-1):path[t]=back[t][path[t+1],path[t+2]]
    else:
        path=_traceback_device(back,forward[-1].reshape(-1).argmax(),k)
    return ids.gather(1,path[:,None]).squeeze(1)


def _traceback_device(back,last,k):
    """Trace pair states without converting GPU indices to host scalars."""
    pair=last.reshape(1)
    reverse=[(pair%k).squeeze(0),(pair//k).squeeze(0)]
    for predecessors in reversed(back):
        # A one-element tensor gather keeps the index on the GPU. Scalar
        # tensor indexing can otherwise synchronize with the host each hop.
        previous=predecessors.reshape(-1).gather(0,pair)
        reverse.append(previous.squeeze(0))
        pair=previous*k+pair//k
    return torch.stack(reverse[::-1])


def sample_second_order(ids,emissions,edges,triples,temperature=1.):
    if temperature==0:return decode_second_order(ids,emissions,edges,triples)
    unary,edges,triples=_potentials(emissions,edges,triples,temperature)
    if len(ids)==1:
        index=torch.multinomial(unary[0].softmax(-1),1)
        return ids[0,index]
    forward,_=_forward(unary,edges,triples)
    k=ids.shape[1];path=torch.empty(len(ids),device=ids.device,dtype=torch.long)
    last=torch.multinomial(forward[-1].reshape(-1).softmax(-1),1).squeeze(0)
    path[-2]=last//k;path[-1]=last%k
    for t in range(len(ids)-3,-1,-1):
        scores=forward[t][:,path[t+1]]+triples[t,:,path[t+1],path[t+2]]
        path[t]=torch.multinomial(scores.softmax(-1),1).squeeze(0)
    return ids.gather(1,path[:,None]).squeeze(1)


def second_order_marginals(emissions,edges,triples,temperature=1.,*,maximum=False):
    """Return pair log-potentials (max) or normalized joint pair probabilities."""
    unary,edges,triples=_potentials(emissions,edges,triples,temperature or 1.)
    if len(unary)<2:return edges.clone()
    forward,_=_forward(unary,edges,triples,maximum=maximum)
    backward=[None]*(len(unary)-1);backward[-1]=torch.zeros_like(edges[-1])
    for t in range(len(unary)-3,-1,-1):
        scores=triples[t]+edges[t+1][None,:,:]+unary[t+2,None,None,:]+backward[t+1][None,:,:]
        row=scores.max(-1).values if maximum else torch.logsumexp(scores,-1)
        backward[t]=row-row.max()
    pair_scores=torch.stack([a+b for a,b in zip(forward,backward)])
    return pair_scores if maximum else pair_scores.flatten(1).softmax(-1).reshape_as(pair_scores)


def second_order_path_margins(ids,emissions,edges,triples,selected):
    if len(ids)==1:
        from .bigram import BigramViterbiSelector
        return BigramViterbiSelector.path_margins(ids,emissions,edges,selected,1.)
    pairs=second_order_marginals(emissions,edges,triples,maximum=True)
    scores=torch.cat((pairs[0].max(1).values[None,:],pairs.max(1).values),0)
    same=ids==selected[:,None]
    return (scores.masked_fill(~same,-torch.inf).max(-1).values-scores.masked_fill(same,-torch.inf).max(-1).values).clamp_min(0.)
