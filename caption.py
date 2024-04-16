import tensorflow as tf

import os
import shutil
from pathlib import Path

import pickle


def standardize(s):
        s = tf.strings.lower(s)
        s = tf.strings.regex_replace(s, f'[{re.escape(string.punctuation)}]', '')
        s = tf.strings.join(['[START]', s, '[END]'], separator=' ')
        return s


# Building the model
class SeqEmbedding(tf.keras.layers.Layer):
    def __init__(self, vocab_size, max_length, depth):
        super().__init__()
        self.pos_embedding = tf.keras.layers.Embedding(input_dim=max_length, output_dim=depth)
        
        self.token_embedding = tf.keras.layers.Embedding(
            input_dim=vocab_size,
            output_dim=depth,
            mask_zero=True)
        
        self.add = tf.keras.layers.Add()
    

    def call(self, seq):
        seq = self.token_embedding(seq) # (batch, seq, depth)
        
        x = tf.range(tf.shape(seq)[1])  # (seq)
        x = x[tf.newaxis, :]  # (1, seq)
        x = self.pos_embedding(x)  # (1, seq, depth)
        
        return self.add([seq, x])


class BaseAttention(tf.keras.layers.Layer):
    def __init__(self, **kwargs):
        super().__init__()
        self.mha = tf.keras.layers.MultiHeadAttention(**kwargs)
        self.layernorm = tf.keras.layers.LayerNormalization()
        self.add = tf.keras.layers.Add()


class CausalSelfAttention(BaseAttention):
    def call(self, x):
        attn = self.mha(query=x, value=x,
                        use_causal_mask=True)
        x = self.add([x, attn])
        return self.layernorm(x)


class CrossAttention(BaseAttention):
    def call(self, x, y, **kwargs):
        attn, attention_scores = self.mha(
                 query=x, value=y,
                 return_attention_scores=True)
        
        self.last_attention_scores = attention_scores
        
        x = self.add([x, attn])
        return self.layernorm(x)


class FeedForward(tf.keras.layers.Layer):
    def __init__(self, units, dropout_rate=0.1):
        super().__init__()
        self.seq = tf.keras.Sequential([
            tf.keras.layers.Dense(units=2*units, activation='relu'),
            tf.keras.layers.Dense(units=units),
            tf.keras.layers.Dropout(rate=dropout_rate),
        ])
        self.add = tf.keras.layers.Add()
        self.layernorm = tf.keras.layers.LayerNormalization()
    

    def call(self, x):
        x = self.add([x, self.seq(x)])
        return self.layernorm(x)


class DecoderLayer(tf.keras.layers.Layer):
    def __init__(self, units, num_heads=1, dropout_rate=0.1):
        super().__init__()
        
        self.self_attention = CausalSelfAttention(num_heads=num_heads,
                                                  key_dim=units,
                                                  dropout=dropout_rate)
        self.cross_attention = CrossAttention(num_heads=num_heads,
                                              key_dim=units,
                                              dropout=dropout_rate)
        self.ff = FeedForward(units=units, dropout_rate=dropout_rate)
    
    
    def call(self, inputs, training=False):
        in_seq, out_seq = inputs
        
        # Text input
        out_seq = self.self_attention(out_seq)
        out_seq = self.cross_attention(out_seq, in_seq)
        self.last_attention_scores = self.cross_attention.last_attention_scores
        out_seq = self.ff(out_seq)
        return out_seq


class Captioner(tf.keras.Model):
    def __init__(self, tokenizer, feature_extractor, output_layer, num_layers=1,
               units=256, max_length=50, num_heads=1, dropout_rate=0.1):
        super().__init__()
        self.feature_extractor = feature_extractor
        self.tokenizer = tokenizer
        self.word_to_index = tf.keras.layers.StringLookup(
            mask_token="",
            vocabulary=tokenizer.get_vocabulary())
        self.index_to_word = tf.keras.layers.StringLookup(
            mask_token="",
            vocabulary=tokenizer.get_vocabulary(),
            invert=True) 
        
        self.seq_embedding = SeqEmbedding(
            vocab_size=tokenizer.vocabulary_size(),
            depth=units,
            max_length=max_length)
        
        self.decoder_layers = [
            DecoderLayer(units, num_heads=num_heads, dropout_rate=dropout_rate)
            for n in range(num_layers)]
        
        self.output_layer = output_layer
    

    def simple_gen(self, image):
        initial = self.word_to_index([['[START]']]) # (batch, sequence)
        img_features = self.feature_extractor(image[tf.newaxis, ...])
        
        tokens = initial # (batch, sequence)
        for n in range(50): # 50 words
            preds = self((img_features, tokens)).numpy()  # (batch, sequence, vocab)
            preds = preds[:,-1, :]  #(batch, vocab)

            next = tf.argmax(preds, axis=-1)[:, tf.newaxis]
            tokens = tf.concat([tokens, next], axis=1) # (batch, sequence) 
            
            if next[0] == self.word_to_index('[END]'):
                break
        words = self.index_to_word(tokens[0, 1:-1])
        result = tf.strings.reduce_join(words, axis=-1, separator=' ')
        return result.numpy().decode()
    

    def call(self, inputs):
        image, txt = inputs

        if image.shape[-1] == 3:
        # Apply the feature-extractor, if you get an RGB image.
            image = self.feature_extractor(image)
        
        # Flatten the feature map
        image = einops.rearrange(image, 'b h w c -> b (h w) c')
        
        
        if txt.dtype == tf.string:
        # Apply the tokenizer if you get string inputs.
            txt = tokenizer(txt)
        
        txt = self.seq_embedding(txt)
        
        # Look at the image
        for dec_layer in self.decoder_layers:
            txt = dec_layer(inputs=(image, txt))
        
        txt = self.output_layer(txt)
        
        return txt


if __name__ == '__main__':
    model_data_path = Path.cwd() / 'Model/Model_Data'
    weights_path = model_data_path / 'weights'

    IMAGE_SHAPE=(224, 224, 3)
    mobilenet = tf.keras.applications.MobileNetV3Large(
        input_shape=IMAGE_SHAPE,
        include_top=False,
        include_preprocessing=True)
    mobilenet.trainable=False

    # Easier file handling
    if not os.path.exists(Path.cwd() / 'Model_Data'):
        os.mkdir(Path.cwd() / 'Model_Data')
    shutil.move(Path.home() / '.keras/models/weights_mobilenet_v3_large_224_1.0_float_no_top_v2.h5', Path.cwd() / 'Model_Data/mobilenet_v3_large_weights.h5')


    from_disk = pickle.load(open(str(pathlib.Path.cwd() / 'Model_Data/tokenizer.pkl'), "rb"))
    tokenizer = tf.keras.layers.TextVectorization(
        max_tokens=from_disk['config']['max_tokens'],
        standardize=standardize,
        ragged=True)
    tokenizer.set_weights(from_disk['weights'])

    # Model
    model = Captioner(tokenizer, feature_extractor=mobilenet, output_layer=output_layer,
                  units=256, dropout_rate=0.5, num_layers=2, num_heads=2)