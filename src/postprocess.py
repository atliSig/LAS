import editdistance as ed
import numpy as np
import torch

from preprocess import ALL_CHARS, EOS_TKN, SOS_TKN, TOKENS


class Hypothesis:
    '''
    Hypothesis for beam search decoding.
    Stores the history of label sequence & score 
    Stores the previous decoder state, ctc state, ctc score, 
    lm state.
    '''
    
    def __init__(self, decoder_state, emb, output_seq=[],
        output_scores=[], lm_state=None):
        
        assert len(output_seq) == len(output_scores)

        self.decoder_state = decoder_state
        self.lm_state = lm_state
        
        # Previous outputs
        self.output_seq = output_seq
        self.output_scores = output_scores
                
        # Embedding layer for last_char
        self.emb = emb
        

    def avg_score(self):
        '''
        Return the averaged log probability of hypothesis
        '''
        assert len(self.output_scores) != 0
        return sum(self.output_scores) / len(self.output_scores)

    def add_topk(self, top_idx, top_vals, decoder_state, lm_state=None):
        '''
        Expand current hypothesis with a given beam size
        
        '''
        new_hyps = []
        term_score = None
        beam_size = len(topi[0])
        
        for i in range(beam_size):
            # Detect <eos>
            if top_idx[0][i].item() == 1:
                term_score = top_vals[0][i].cpu()
                continue
            
            idxes = self.output_seq[:]     # pass by value
            scores = self.output_scores[:] # pass by value
            idxes.append(top_idx[0][i].cpu())
            scores.append(top_vals[0][i].cpu()) 
            new_hyps.append(Hypothesis(decoder_state, self.emb,
                output_seq=idxes, output_scores=scores, lm_state=lm_state))
        
        if term_score is not None:
            self.output_seq.append(torch.tensor(1))
            self.output_scores.append(term_score)
            return self, new_hyps
        
        return None, new_hyps

    @property
    def last_char_idx(self):
        idx = self.output_seq[-1] if len(self.output_seq) != 0 else 0
        return torch.LongTensor([[idx]])
    @property
    def last_char(self):
        idx = self.output_seq[-1] if len(self.output_seq) != 0 else 0
        return self.emb(torch.LongTensor([idx]).to(next(self.emb.parameters()).device))


def calc_acc(predict, label):
    '''
    Input arguments:
    * predict: A [batch_size, seq_len, char_dim] tensor, representing
    the prediction made for the label
    * label:  A [batch_size, seq_len] of mapped characters to indexes

    Returns the character-level accuracy of the prediction for 
    the whole batch.
    '''
    predict = np.argmax(predict.cpu().detach(),axis=-1)
    label = label.cpu()
    accs = []
    for p,l in zip(predict,label):
        correct = 0.0
        total_char = 0
        for pp,ll in zip(p,l):
            if ll == 0: break
            correct += int(pp==ll)
            total_char += 1
        accs.append(correct/total_char)
    
    return sum(accs)/len(accs)

def calc_err(predict, label, mapper):
    '''
    Input arguments:
    * predict: A [batch_size, seq_len, char_dim] tensor, representing
    the prediction made for the label
    * label:  A [batch_size, seq_len] of mapped characters to indexes

    Returns the error rate in terms of edit distance for word-by-word
    comparisons between predictions and labels for each sample in the
    batch
    '''
    label = label.cpu()
    predict = np.argmax(predict.cpu().detach(), axis=-1)
    predict = [mapper.translate(p) for p in predict]
    label = [mapper.translate(l) for l in label]

    ds = [float(ed.eval(p.split(' '), l.split(' '))) / len(l.split(' ')) 
        for p,l in zip(predict,label)]
    
    return sum(ds)/len(ds)

def draw_att(att, hyp_txt):
    # TODO: THIS IS PROBS BROKEN
    attmaps = []
    for att,hyp in zip(att, np.argmax(hyp_txt.cpu().detach(),axis=-1)):
        # the length without any trailing symbols after EOS token
        att_len = len(trim_eos(hyp))
        att = att.detach().cpu()
        attmaps.append(torch.stack([att,att,att],dim=0)[:,:att_len,:]) # +1 for att. @ <eos>
    return attmaps

def trim_eos(sequence):
    new_pred = []
    for char in sequence:
        new_pred.append(int(char))
        # HACK: 1 maps to '>', generally speaking
        if char == 1:
            break
    return new_pred
