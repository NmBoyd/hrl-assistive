#!/usr/bin/env python
#
# Copyright (c) 2014, Georgia Tech Research Corporation
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Georgia Tech Research Corporation nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY GEORGIA TECH RESEARCH CORPORATION ''AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL GEORGIA TECH BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

#  \author Daehyung Park (Healthcare Robotics Lab, Georgia Tech.)

# system & utils
import os, sys, copy, random
import numpy
import numpy as np
import scipy

# Keras
import h5py 
from keras.models import Sequential, Model
from keras.layers import Merge, Input, TimeDistributed, Layer
from keras.layers import Activation, Dropout, Flatten, Dense, merge, Lambda, RepeatVector, LSTM
from keras.layers.advanced_activations import PReLU, LeakyReLU
from keras.utils.np_utils import to_categorical
from keras.optimizers import SGD, Adagrad, Adadelta, RMSprop, Adam
from keras import backend as K
from keras import objectives

from hrl_anomaly_detection.RAL18_detection import keras_util as ku

import gc



def lstm_vae3(trainData, testData, weights_file=None, batch_size=1024, nb_epoch=500, \
              patience=20, fine_tuning=False, save_weights_file=None, steps_per_epoch=512):
    """
    Variational Autoencoder with two LSTMs and one fully-connected layer
    x_train is (sample x length x dim)
    x_test is (sample x length x dim)
    """    
    x_train = trainData[0]
    y_train = trainData[1]
    x_test = testData[0]
    y_test = testData[1]

    timesteps = len(x_train[0])
    input_dim = len(x_train[0][0])

    h1_dim = input_dim
    h2_dim = 2 #input_dim
    z_dim  = 2

    inputs = Input(shape=(timesteps, input_dim))
    encoded = LSTM(h1_dim, return_sequences=True, activation='tanh')(inputs)
    encoded = LSTM(h2_dim, return_sequences=False, activation='tanh')(encoded)
    z_mean  = Dense(z_dim)(encoded) #, activation='tanh'
    z_log_var = Dense(z_dim)(encoded) #, activation='sigmoid')
    
    def sampling(args):
        z_mean, z_log_var = args
        epsilon = K.random_normal(shape=K.shape(z_mean), mean=0., stddev=1.0)
        ## epsilon = K.random_normal(shape=(z_dim,), mean=0., stddev=1.0)
        return z_mean + K.exp(z_log_var/2.0) * epsilon    
        
    # we initiate these layers to reuse later.
    decoded_h1 = Dense(h2_dim, name='h_1') #, activation='tanh'
    decoded_h2 = RepeatVector(timesteps, name='h_2')
    decoded_L1 = LSTM(h1_dim, return_sequences=True, name='L_1')
    decoded_L21 = LSTM(input_dim, return_sequences=True, name='L_21')
    decoded_L22 = LSTM(input_dim, return_sequences=True, activation='sigmoid', name='L_22')

    # Custom loss layer
    class CustomVariationalLayer(Layer):
        def __init__(self, **kwargs):
            self.is_placeholder = True
            super(CustomVariationalLayer, self).__init__(**kwargs)

        def vae_loss(self, x, x_d_mean, x_d_log_var):
            log_p_x_z = -0.5 * ( K.sum(K.square((x-x_d_mean))/K.exp(x_d_log_var-1e-10), axis=-1) \
                                 + float(input_dim) * K.log(2.0*np.pi) + K.sum(x_d_log_var-1e-10, axis=-1) )
            ## xent_loss = K.sum(-log_p_x_z, axis=-1)
            ## xent_loss = K.mean(-log_p_x_z, axis=-1)
            xent_loss = K.mean(-log_p_x_z, axis=-1)
            ## xent_loss = K.mean(K.sum(K.square(x_d_mean - x), axis=-1), axis=-1)
            
            kl_loss = - 0.5 * K.sum(1 + z_log_var - K.square(z_mean) - K.exp(z_log_var), axis=-1)
            ## var_loss = K.mean(K.sum(K.exp(x_d_log_var), axis=-1))
            ## return xent_loss + kl_loss # + var_loss*10.0)
            return K.mean(xent_loss + kl_loss) # + var_loss*10.0)

        def call(self, args):
            x = args[0]
            x_d_mean    = args[1]
            x_d_log_var = args[2] # relu outputs positives only. So multiply -1
            
            loss = self.vae_loss(x, x_d_mean, x_d_log_var)
            self.add_loss(loss, inputs=args)
            # We won't actually use the output.
            return x_d_mean


    z = Lambda(sampling)([z_mean, z_log_var])    
    decoded = decoded_h1(z)
    decoded = decoded_h2(decoded)
    decoded = decoded_L1(decoded)
    decoded_mean   = decoded_L21(decoded)
    decoded_logvar = decoded_L22(decoded)
    outputs = CustomVariationalLayer()([inputs, decoded_mean, decoded_logvar])

    vae_autoencoder = Model(inputs, outputs)
    print(vae_autoencoder.summary())

    # Encoder --------------------------------------------------
    vae_encoder_mean = Model(inputs, z_mean)
    vae_encoder_var  = Model(inputs, z_log_var)

    # Decoder (generator) --------------------------------------
    decoder_input = Input(shape=(z_dim,))
    _decoded_H1 = decoded_h1(decoder_input)
    _decoded_H2 = decoded_h2(_decoded_H1)
    _decoded_L1 = decoded_L1(_decoded_H2)
    _decoded_L2 = decoded_L21(_decoded_L1)
    generator = Model(decoder_input, _decoded_L2)

    # VAE --------------------------------------
    vae_mean   = Model(inputs, decoded_mean)
    vae_logvar = Model(inputs, decoded_logvar)


    if weights_file is not None and os.path.isfile(weights_file) and fine_tuning is False:
        vae_autoencoder.load_weights(weights_file)
        return vae_autoencoder, vae_mean, vae_logvar, vae_encoder_mean, vae_encoder_var, generator
    else:
        #vae_autoencoder.load_weights(weights_file)
        if fine_tuning:
            vae_autoencoder.load_weights(weights_file)
            lr = 0.001
        else:
            lr = 0.001
        #optimizer = RMSprop(lr=lr, rho=0.9, epsilon=1e-08, decay=0.0001)
        optimizer = Adam(lr=lr)                
        vae_autoencoder.compile(optimizer=optimizer, loss=None)
        #vae_autoencoder.compile(optimizer='sgd', loss=None)

        ## vae_autoencoder.load_weights(weights_file)
        from keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
        callbacks = [EarlyStopping(monitor='val_loss', min_delta=0, patience=patience,
                                   verbose=0, mode='auto'),
                    ModelCheckpoint(weights_file,
                                    save_best_only=True,
                                    save_weights_only=True,
                                    monitor='val_loss'),
                    ReduceLROnPlateau(monitor='val_loss', factor=0.5,
                                      patience=2, min_lr=0.0)]

        train_datagen = ku.sigGenerator(augmentation=True, noise_mag=0.03)
        train_generator = train_datagen.flow(x_train, x_train, batch_size=batch_size, seed=3334)
        ## test_datagen = ku.sigGenerator(augmentation=False)
        ## test_generator = test_datagen.flow(x_test, x_test, batch_size=len(x_test),
                                           ## shuffle=False)

        ## vae_autoencoder.fit(x_train, x_train,
        ##                     shuffle=True,
        ##                     epochs=nb_epoch,
        ##                     batch_size=batch_size,
        ##                     callbacks=callbacks,
        ##                     validation_data=(x_test, x_test))

        hist = vae_autoencoder.fit_generator(train_generator,
                                             steps_per_epoch=steps_per_epoch,
                                             epochs=nb_epoch,
                                             validation_data=(x_test, x_test),
                                             ## validation_data=test_generator,
                                             ## validation_steps=1,
                                             callbacks=callbacks)
        if save_weights_file is not None:
            vae_autoencoder.save_weights(save_weights_file)
        else:
            vae_autoencoder.save_weights(weights_file)

        gc.collect()
        
        return vae_autoencoder, vae_mean, vae_logvar, vae_encoder_mean, vae_encoder_var, generator


def lstm_vae4(trainData, testData, weights_file=None, batch_size=1024, nb_epoch=500, \
              patience=20, fine_tuning=False, save_weights_file=None):
    """
    Variational Autoencoder with two LSTMs and one fully-connected layer
    x_train is (sample x length x dim)
    x_test is (sample x length x dim)
    """
    ## import tensorflow as tf
    ## sess = tf.Session()
    ## K.set_session(sess)
    
    x_train = trainData[0]
    y_train = trainData[1]
    x_test = testData[0]
    y_test = testData[1]

    timesteps = len(x_train[0])
    input_dim = len(x_train[0][0])

    h1_dim = input_dim
    z_dim  = 2

    inputs    = Input(shape=(timesteps, input_dim))
    encoded   = LSTM(h1_dim, return_sequences=False, activation='tanh')(inputs)
    z_mean    = Dense(z_dim)(encoded) 
    z_log_var = Dense(z_dim)(encoded) 
    
    def sampling(args):
        z_mean, z_log_var = args
        epsilon = K.random_normal(shape=(z_dim,), mean=0., stddev=1.0)
        return z_mean + K.exp(z_log_var/2.0) * epsilon    
        
    # we initiate these layers to reuse later.
    decoded_h1  = Dense(z_dim, name='h_1') #, activation='tanh'
    decoded_h2  = RepeatVector(timesteps, name='h_2')
    decoded_L21 = LSTM(input_dim, return_sequences=True, activation='tanh', name='L_21')
    decoded_L22 = LSTM(input_dim, return_sequences=True, activation='tanh', name='L_22')


    # Custom loss layer
    class CustomVariationalLayer(Layer):
        def __init__(self, **kwargs):
            self.is_placeholder = True
            super(CustomVariationalLayer, self).__init__(**kwargs)

        def vae_loss(self, x, x_d_mean, x_d_log_var):
            log_p_x_z = -0.5 * ( K.sum(K.square((x-x_d_mean))/K.exp(x_d_log_var), axis=-1) \
                                 + float(input_dim) * K.log(2.0*np.pi) + K.sum(x_d_log_var, axis=-1) )
            ## xent_loss = K.sum(-log_p_x_z, axis=-1)
            xent_loss = K.mean(-log_p_x_z, axis=-1)
            ## xent_loss = K.mean(K.sum(K.square(x_d_mean - x), axis=-1), axis=-1)
            kl_loss = - 0.5 * K.sum(1 + z_log_var - K.square(z_mean) - K.exp(z_log_var), axis=-1)
            return K.mean(xent_loss + kl_loss)

        def call(self, args):
            x = args[0]
            x_d_mean    = args[1]
            x_d_log_var = args[2]
            
            loss = self.vae_loss(x, x_d_mean, x_d_log_var)
            self.add_loss(loss, inputs=args)
            # We won't actually use the output.
            return x_d_mean


    z = Lambda(sampling)([z_mean, z_log_var])    
    decoded = decoded_h1(z)
    decoded = decoded_h2(decoded)
    decoded_mean   = decoded_L21(decoded)
    decoded_logvar = decoded_L22(decoded)
    outputs = CustomVariationalLayer()([inputs, decoded_mean, decoded_logvar])

    vae_autoencoder = Model(inputs, outputs)
    print(vae_autoencoder.summary())

    # Encoder --------------------------------------------------
    vae_encoder_mean = Model(inputs, z_mean)
    vae_encoder_var  = Model(inputs, z_log_var)

    # Decoder (generator) --------------------------------------
    decoder_input = Input(shape=(z_dim,))
    _decoded_H1 = decoded_h1(decoder_input)
    _decoded_H2 = decoded_h2(_decoded_H1)
    _decoded_L2 = decoded_L21(_decoded_H2)
    generator = Model(decoder_input, _decoded_L2)

    # VAE --------------------------------------
    vae_mean   = Model(inputs, decoded_mean)
    vae_logvar = Model(inputs, decoded_logvar)


    if weights_file is not None and os.path.isfile(weights_file) and fine_tuning is False:
        vae_autoencoder.load_weights(weights_file)
        return vae_autoencoder, vae_mean, vae_logvar, vae_encoder_mean, vae_encoder_var, generator
    else:
        ## vae_autoencoder.load_weights(weights_file)
        if fine_tuning:
            vae_autoencoder.load_weights(weights_file)
            lr = 0.001
        else:
            lr = 0.01
        optimizer = RMSprop(lr=lr, rho=0.9, epsilon=1e-08, decay=0.0001)
        #optimizer = Adam(lr=lr)                
        vae_autoencoder.compile(optimizer=optimizer, loss=None)

        ## vae_autoencoder.load_weights(weights_file)
        from keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
        callbacks = [EarlyStopping(monitor='val_loss', min_delta=0, patience=patience,
                                   verbose=0, mode='auto'),
                    ModelCheckpoint(weights_file,
                                    save_best_only=True,
                                    save_weights_only=True,
                                    monitor='val_loss'),
                    ReduceLROnPlateau(monitor='val_loss', factor=0.2,
                                      patience=3, min_lr=0.0001)]

        train_datagen = ku.sigGenerator(augmentation=True, noise_mag=0.05)
        train_generator = train_datagen.flow(x_train, x_train, batch_size=batch_size, seed=3334)
        ## test_datagen = ku.sigGenerator(augmentation=False)
        ## test_generator = test_datagen.flow(x_test, x_test, batch_size=len(x_test),
                                           ## shuffle=False)

        hist = vae_autoencoder.fit_generator(train_generator,
                                             steps_per_epoch=2048,
                                             epochs=nb_epoch,
                                             validation_data=(x_test, x_test),
                                             ## validation_data=test_generator,
                                             ## validation_steps=1,
                                             callbacks=callbacks)
        if save_weights_file is not None:
            vae_autoencoder.save_weights(save_weights_file)
        else:
            vae_autoencoder.save_weights(weights_file)

        gc.collect()
        
        return vae_autoencoder, vae_mean, vae_logvar, vae_encoder_mean, vae_encoder_var, generator



def lstm_ae(trainData, testData, weights_file=None, batch_size=1024, nb_epoch=500, patience=20,
             fine_tuning=False, save_weights_file=None):
    """
    Variational Autoencoder with two LSTMs and one fully-connected layer
    x_train is (sample x length x dim)
    x_test is (sample x length x dim)

    Note: it uses offline data.
    This code based on "https://gist.github.com/tushuhei/e684c2a5382c324880532aded9faf4e6"
    """
    x_train = trainData[0]
    y_train = trainData[1]
    x_test = testData[0]
    y_test = testData[1]

    timesteps = len(x_train[0])
    input_dim = len(x_train[0][0])

    h1_dim = input_dim
    z_dim  = 2
    
    inputs = Input(shape=(timesteps, input_dim))
    encoded = LSTM(h1_dim, return_sequences=True, activation='tanh')(inputs)
    encoded = LSTM(z_dim, return_sequences=False, activation='tanh')(encoded)
        
    # we initiate these layers to reuse later.
    decoded_H2 = RepeatVector(timesteps, name='H_2')
    decoded_L1 = LSTM(h1_dim, return_sequences=True, activation='tanh', name='L_1')
    decoded_L2 = LSTM(input_dim, return_sequences=True, activation='tanh', name='L_2')

    decoded = decoded_H2(encoded)
    decoded = decoded_L1(decoded)
    decoded = decoded_L2(decoded)
    
    ae = Model(inputs, decoded)
    print(ae.summary())

    if weights_file is not None and os.path.isfile(weights_file) and fine_tuning is False:
        ae.load_weights(weights_file)
        #generator.load_weights(weights_file, by_name=True)
        return ae
    else:
        if fine_tuning:
            ae.load_weights(weights_file)
            lr = 0.001
        else:
            lr = 0.1
        ## optimizer = RMSprop(lr=lr, rho=0.9, epsilon=1e-08, decay=0.0001)
        ## #optimizer = Adam(lr=lr)                
        ## ae.compile(optimizer=optimizer, loss='mse')
        ae.compile(loss='mean_squared_error', optimizer='adam')
        #ae.compile(loss=vae_loss, optimizer='adam')
            
        ## vae_autoencoder.load_weights(weights_file)
        from keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
        callbacks = [EarlyStopping(monitor='val_loss', min_delta=0, patience=patience,
                                   verbose=0, mode='auto'),
                    ModelCheckpoint(weights_file,
                                    save_best_only=True,
                                    save_weights_only=True,
                                    monitor='val_loss'),
                    ReduceLROnPlateau(monitor='val_loss', factor=0.2,
                                      patience=5, min_lr=0.0001)]

        train_datagen = ku.sigGenerator(augmentation=True, noise_mag=0.05 )
        #test_datagen = ku.sigGenerator(augmentation=False)
        train_generator = train_datagen.flow(x_train, x_train, batch_size=batch_size)
        #test_generator = test_datagen.flow(x_test, x_test, batch_size=batch_size, shuffle=False)

        hist = ae.fit_generator(train_generator,
                                samples_per_epoch=512,
                                epochs=nb_epoch,
                                validation_data=(x_test, x_test),
                                #validation_data=test_generator,
                                #nb_val_samples=len(x_test),
                                callbacks=callbacks) #, class_weight=class_weight)

        ## ae.fit(x_train, x_train,
        ##        shuffle=True,
        ##        epochs=nb_epoch,
        ##        batch_size=batch_size,
        ##        callbacks=callbacks,
        ##        validation_data=(x_test, x_test))
        if save_weights_file is not None:
            ae.save_weights(save_weights_file)
        else:
            ae.save_weights(weights_file)

        gc.collect()
        
        return ae


