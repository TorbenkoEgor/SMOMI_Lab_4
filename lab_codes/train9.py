"""This module implements data feeding and training loop to create model
to classify X-Ray chest images as a lab example for BSU students.
"""

__author__ = 'Alexander Soroka, soroka.a.m@gmail.com'
__copyright__ = """Copyright 2020 Alexander Soroka"""


import argparse
import glob
import numpy as np
import tensorflow as tf
import time
from tensorflow.python import keras as keras
from tensorflow.python.keras.callbacks import LearningRateScheduler


LOG_DIR = 'logs'
SHUFFLE_BUFFER = 4
BATCH_SIZE = 72
NUM_CLASSES = 6
PARALLEL_CALLS=4
RESIZE_TO = 224
TRAINSET_SIZE = 14034
VALSET_SIZE = 3000


def parse_proto_example(proto):
    keys_to_features = {
        'image/encoded': tf.io.FixedLenFeature((), tf.string, default_value=''),
        'image/class/label': tf.io.FixedLenFeature([], tf.int64, default_value=tf.zeros([], dtype=tf.int64))
    }
    example = tf.io.parse_single_example(proto, keys_to_features)
    example['image'] = tf.image.decode_jpeg(example['image/encoded'], channels=3)
    example['image'] = tf.image.convert_image_dtype(example['image'], dtype=tf.float32)
    example['image'] = tf.image.resize(example['image'], tf.constant([RESIZE_TO, RESIZE_TO]))
    return example['image'], tf.one_hot(example['image/class/label'], depth=NUM_CLASSES)


def normalize(image, label):
    return tf.image.per_image_standardization(image), label

def resize(image, label):
    return tf.image.resize(image, tf.constant([RESIZE_TO, RESIZE_TO])), label

def create_dataset(filenames, batch_size):
    """Create dataset from tfrecords file
    :tfrecords_files: Mask to collect tfrecords file of dataset
    :returns: tf.data.Dataset
    """
    return tf.data.TFRecordDataset(filenames)\
        .map(parse_proto_example)\
        .map(resize)\
        .map(normalize)\
        .batch(batch_size)\
        .prefetch(batch_size)

def create_aug_dataset(filenames, batch_size):
    return tf.data.TFRecordDataset(filenames)\
        .map(parse_proto_example)\
        .map(resize)\
        .map(normalize)\
        .map(augment)\
        .shuffle(buffer_size=5 * batch_size)\
        .batch(batch_size)\
        .prefetch(2 * batch_size)

def augment(image,label):
    with tf.name_scope('Add_gaussian_noise'): 
        noise_img = image + tf.random.normal(shape=tf.shape(image), mean=0.0, stddev=(100)/(255), dtype=tf.float32)
        noise_img = tf.clip_by_value(noise_img, 0.0, 1.0)
    return noise_img,label

def build_model():
    base_model = tf.keras.applications.MobileNetV2(input_shape=(224,224,3),
						classes = NUM_CLASSES,
                                               include_top=False,
                                               weights='imagenet')
    #base_model.trainable = False
    return tf.keras.models.Sequential([
    	base_model,
    	tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(NUM_CLASSES, activation=tf.keras.activations.softmax)
    ])


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--train', type=str, help='Glob pattern to collect train tfrecord files')
    args.add_argument('--test', type=str, help='Glob pattern to collect test tfrecord files')
    args = args.parse_args()

    train_dataset = create_aug_dataset(glob.glob(args.train), BATCH_SIZE)
    validation_dataset = create_aug_dataset(glob.glob(args.test), BATCH_SIZE)

    model = build_model()

    model.compile(
        optimizer=tf.optimizers.SGD(lr=0.0000023, momentum=0.9),
        loss=tf.keras.losses.categorical_crossentropy,
        metrics=[tf.keras.metrics.categorical_accuracy],
    )

    log_dir='{}/ilcd-{}'.format(LOG_DIR, time.time())
    model.fit(
        train_dataset,
        epochs=75,
        validation_data=validation_dataset,
        callbacks=[
            tf.keras.callbacks.TensorBoard(log_dir),
        ]
    )


if __name__ == '__main__':
    main()
