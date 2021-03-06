import numpy as np 
import os
import skimage.io as io
import skimage.transform as trans
import numpy as np
from tensorflow.keras.models import *
from tensorflow.keras.layers import *
from tensorflow.keras.optimizers import *
from tensorflow.keras.callbacks import ModelCheckpoint, LearningRateScheduler
from tensorflow.keras import backend as K
import tensorflow as tf

def dice_coef(y_true, y_pred, smooth=1):
    intersection = K.sum(y_true * y_pred, axis=[1,2,3])
    union = K.sum(y_true, axis=[1,2,3]) + K.sum(y_pred, axis=[1,2,3])
    return K.mean( (2. * intersection + smooth) / (union + smooth), axis=0)

def dice_coef_loss(y_true, y_pred):
    return 1-dice_coef(y_true, y_pred)
def iou(y_true,y_pred):
	def f(y_true,y_pred):
		intersection = (y_true*y_pred).sum()
		union = y_true.sum() + y_pred.sum() - intersection
		x = (intersection + 1e-15) / (union + 1e-15)
		x = x.astype(np.float32)
		return x
	return tf.numpy_function(f,[y_true,y_pred],tf.float32)

def dilat_conv(x,filter):  
  shape = x.shape
  y1 = AveragePooling2D(pool_size=(shape[1],shape[2]))(x)
  y1 = Conv2D(filter,2,padding='same')(y1)
  y1 = BatchNormalization()(y1)
  y1 = UpSampling2D((shape[1],shape[2]),interpolation='bilinear')(y1)  #dilation_rate =1 is normal convolution
  y2 = Conv2D(filter,1,dilation_rate = 1,padding='same',use_bias=False)(x)
  y2 = BatchNormalization()(y2)  
  y3 = Conv2D(filter,3,dilation_rate = 6,padding='same',use_bias=False)(x)
  y3 = BatchNormalization()(y3)
  y4 = Conv2D(filter,3,dilation_rate = 12,padding='same',use_bias=False)(x)
  y4 = BatchNormalization()(y4)
  y5 = Conv2D(filter,3,dilation_rate = 18,padding='same',use_bias=False)(x)
  y5 = BatchNormalization()(y5) 
  y = Concatenate()([y1,y2,y3,y4,y5])
  
  y = Conv2D(filter,1,dilation_rate = 1,padding='same',use_bias=False)(y)
  y = BatchNormalization()(y)
  return y

def conv_block(cur_conv, prev_conv, filters):
       # cur_conv = Conv2D(filters, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(prev_conv)
    merge = concatenate([cur_conv,prev_conv], axis = 3)
    cur_conv = Conv2D(filters, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(merge)
    cur_conv = MaxPooling2D(pool_size=(1, 1))(merge)
    cur_conv = Conv2D(filters, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(cur_conv)
    cur_conv = BatchNormalization()(cur_conv)
    #cur_conv = Dropout(0.3)(cur_conv)
    return cur_conv

def unet(pretrained_weights = None,input_size=(512,512,3), n_class=3):
    inputs = tf.keras.Input(shape=(512,512,3))
    conv1 = Conv2D(32, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(inputs)
    conv2 = Conv2D(64, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(inputs)
    conv3 = Conv2D(128, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(inputs)

    conv1 = conv_block(conv1, conv1, 32)
    conv2 = conv_block(conv2, conv1, 64)
    conv3 = conv_block(conv3, conv1, 128)
    y = Concatenate()([conv1,conv2,conv3])
    y = dilat_conv(y,8)
    conv1 = conv_block(conv1, y, 32)
    conv2 = conv_block(conv2, y, 64)
    conv3 = conv_block(conv3, y, 128)
    y = Concatenate()([conv1,conv2,conv3])
    #y = dilat_conv(y,8)
    drop = Dropout(0.2)(y)
    y = dilat_conv(drop,8)

    
    up3 = Conv2D(64, 2, activation = 'relu', padding = 'same', 
                 kernel_initializer = 'he_normal')(UpSampling2D(size = (1,1))(y))
    merge3 = concatenate([y,up3], axis = 3)
    conv4 = Conv2D(64, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(merge3)
    merge3 = concatenate([conv3,conv4], axis = 3)
    conv4 = Conv2D(64, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(conv4)
    
    up2 = Conv2D(32, 2, activation = 'relu', padding = 'same',kernel_initializer = 'he_normal')(UpSampling2D(size = (1,1))(conv4))
    merge2 = concatenate([conv3,up2], axis = 3)
    conv5 = Conv2D(32, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(merge2)
    merge2 = concatenate([conv3,conv5], axis = 3)
    conv5 = Conv2D(32, 3, activation = 'relu', padding = 'same', kernel_initializer = 'he_normal')(conv5)
   
    conv6 = Conv2D(n_class, 1, activation = 'sigmoid')(conv5)

    model = tf.keras.Model(inputs = inputs, outputs = conv6)

    model.compile(optimizer = Adam(lr = 0.0001), loss = [dice_coef_loss], metrics = [iou,dice_coef])
    #model.compile(optimizer = Adam(lr = 0.0001), loss = [dice_coef_loss], metrics = [dice_coef])
    if(pretrained_weights):
    	model.load_weights(pretrained_weights)

    return model
