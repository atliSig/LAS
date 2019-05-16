import torch
import torch.nn as nn

class Discriminator(nn.Module):
    def __init__(self, in_dim:int, hidden_dim:int=256):
        '''
        Input arguments:
        in_dim (int): The feature dimension of samples supplied as inputs
        to the discriminator
        hidden_dim (int): Number of nodes per layer in the discriminator

        In our model, the discriminator is a simple feed-forward
        network with two fully-connected layers. It takes as input
        a single vector, and outputs a single real-valued score in the
        interval [0, 1]. 
        The discriminator is trained using binary cross-
        entropy loss to assign high scores to output vectors generated
        by the text encoder and low scores to those generated by the
        speech encoder. We use label smoothing
        
        My interpretation is then that the Discriminator 
        'evaluates' each time step of its input, rather than 
        emitting a 0 or 1 per utterance.
        
        Direct quote from Drexler:
        It takes as input a single vector, and outputs a single 
        real-valued score in the interval [0, 1]. The discriminator 
        is trained using binary cross-entropy loss to assign high scores 
        to output vectors generated by the text encoder and low scores 
        to those generated by the speech encoder.

        Reasoning:
        * Listener output (Generator): [batch_size, ~seq/8, 512]
        * Text encoder output (Data distribution): [batch_size. seq, 512]
        '''
        super(Discriminator, self).__init__()

        self.core = nn.Sequential(
            torch.nn.Linear(in_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, 1))

        self.in_layer = torch.rnn.Linear(in_dim, hidden_dim)
        self.l_1 = nn.Linear(hidden_dim, 1)
        #self.l_2 = nn.Linear(hidden_dim, 1)
    
    def forward(self, x):
        '''
        A [batch_size, seq, 512] tensor, containing all frames from 
        each batch from either the Text Encoder or Listener.

        Even though this is put through linear layers, we can keep
        the input 3-dimensional, pytorch just thinks about [bs, *, features]
        as [bs x *, features] (varified)        
        '''
        #out = self.in_layer(x)
        #out = self.l_1(out)
        #out = self.l_1(out)

        out = self.core(x)
        # apply the sigmoid function to get outputs in the (0,1) range
        out = torch.sigmoid(out)
        return out

def test_solver():
    '''
    Adversarial training:
    * (G)enerator: Listener (from LAS)
    * (D)iscriminator: This discriminator module
    * Data distribution: The text encoder

    D is trained to maximize the correct label to samples from
    either G (label = 0 ) or the data distribution (label = 1)
    --> maximize: log(D(x)) + log(1 - D(G(x)))

    G is trained to maximize the error rate of the D.
    --> maximize: log(D(G(z)))

    We use cross entropy loss for both and different optims for each
    '''
    from dataset import load_dataset, prepare_x, prepare_y
    from asr import Listener, Speller, Attention

    from text_autoencoder import TextAutoEncoder

    batch_size = 2

    (mapper, dataset, dataloader) = load_dataset('data/processed/index.tsv', 
        batch_size=2, n_jobs=1, use_gpu=False, text_only=False)

    label_smoothing = 0.1 # real label becomes (1 - label_smoothing)

    # initialize the text_autoenc (Datasource)
    speller = Speller(256, 256*2)
    attention = Attention(128, 256*2, 256)
    char_emb = nn.Embedding(dataset.get_char_dim(), 256)
    char_trans = nn.Linear(256, dataset.get_char_dim())
    
    text_autoenc = TextAutoEncoder(dataset.get_char_dim(), tf_rate=0.9)
    text_autoenc.set_speller(speller)
    text_autoenc.set_attention(attention)
    text_autoenc.set_char_emb(char_emb)
    text_autoenc.set_char_trans(char_trans)

    data_distribution = text_autoenc.encoder

    # initalize the listener (Generator)
    generator = Listener(256, 40)


    # initialize Discriminator
    discriminator = Discriminator(generator.get_outdim(), 256)


    generator_optim = torch.optim.Adam(generator.parameters(), 
        lr=0.01, betas=(0.5, 0.999))
    discriminator_optim = torch.optim.Adam(
        discriminator.parameters(), lr=0.01, betas=(0.5, 0.999))

    criterion = nn.BCELoss()

    for (x, y) in dataloader:

        x, x_lens = prepare_x(x)
        y, y_lens = prepare_y(y)        
        '''
        DISCRIMINATOR TRAINING
        maximize log(D(x)) + log(1 - D(G(z)))
        '''
        discriminator.zero_grad()

        '''Discriminator real data training'''
        real_data = data_distribution(y) # [bs, seq, 512]
        D_out = discriminator(real_data)
        real_labels = torch.ones(batch_size, real_data.shape[1]) - label_smoothing
        D_realloss = criterion(D_out.squeeze(dim=2), real_labels)
        print('Discriminator real loss: {}'.format(D_realloss))
        D_realloss.backward()

        '''Discriminator fake data training'''
        fake_data, _ = generator(x, x_lens)
        # Note: fake_data.detach() is used here to avoid backpropping
        # through the generator. (see grad_pointers.gp_6 for details)
        D_out = discriminator(fake_data.detach())
        fake_labels = torch.zeros(batch_size, fake_data.shape[1])
        D_fakeloss = criterion(D_out.squeeze(dim=2), fake_labels)
        print('Discriminator fake loss: {}'.format(D_fakeloss))
        D_fakeloss.backward()
        
        # update the parameters and collect total loss
        D_totalloss = D_realloss + D_fakeloss
        discriminator_optim.step()

        '''
        GENERATOR TRAINING 
        maximize log(D(G(z)))
        '''
        generator.zero_grad()

        # fake labels for the listener are the true labels for the
        # discriminator 
        fake_labels = torch.ones(batch_size, fake_data.shape[1])
        
        '''
        we cant call .detach() here, to avoid gradient calculations
        on the discriminator, since then we would lose the history needed
        to update the generator.

        x -> G -> fake_data -> D -> D_out -> Calculate loss
        
        vs.

        x -> G -> fake_data -> fake_data.detach()
        [    LOST HISTORY    ]      | -> D -> D_out -> Calculate loss
        '''
        D_out = discriminator(fake_data)

        G_loss = criterion(D_out.squeeze(dim=2), fake_labels)
        print('Generator loss: {}'.format(G_loss))
        print('-------------------------------------')
        G_loss.backward()

        generator_optim.step()

if __name__ == '__main__': 
    test_solver()