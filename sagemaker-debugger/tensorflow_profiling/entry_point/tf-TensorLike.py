# Standard Library
import argparse
import time

# Third Party
import numpy as np
import tensorflow.compat.v2 as tf
from tensorflow.keras.applications.resnet50 import ResNet50
from tensorflow.keras.datasets import cifar10
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.utils import to_categorical

# First Party
from smdebug.tensorflow import KerasHook


def between_steps_bottleneck():
    time.sleep(1)


class CustomCallback(tf.keras.callbacks.Callback):
    def on_train_batch_begin(self, batch, logs=None):
        if 10 <= batch < 20:
            between_steps_bottleneck()


def train(batch_size, epoch, model, enable_bottleneck, data_augmentation):
    callbacks = [CustomCallback()] if enable_bottleneck else []

    (X_train, y_train), (X_valid, y_valid) = cifar10.load_data()

    Y_train = to_categorical(y_train, 10)
    Y_valid = to_categorical(y_valid, 10)

    X_train = X_train.astype("float32")
    X_valid = X_valid.astype("float32")

    mean_image = np.mean(X_train, axis=0)
    X_train -= mean_image
    X_valid -= mean_image
    X_train /= 128.0
    X_valid /= 128.0

    if not data_augmentation:
        model.fit(
            X_train,
            Y_train,
            batch_size=batch_size,
            epochs=epoch,
            validation_data=(X_valid, Y_valid),
            shuffle=True,
        )
    else:
        datagen = ImageDataGenerator(
            zca_whitening=True,
            width_shift_range=0.1,
            height_shift_range=0.1,
            shear_range=0.0,
            zoom_range=0.0,
            channel_shift_range=0.0,
            fill_mode="nearest",
            cval=0.0,
            horizontal_flip=True,
            vertical_flip=True,
            validation_split=0.0,
        )

        datagen.fit(X_train)

        # Fit the model on the batches generated by datagen.flow().
        model.fit_generator(
            datagen.flow(X_train, Y_train, batch_size=batch_size),
            callbacks=callbacks,
            epochs=epoch,
            validation_data=(X_valid, Y_valid),
            workers=1,
        )


def main():
    _ = KerasHook(out_dir="")  # need this line so that import doesn't get removed by pre-commit
    parser = argparse.ArgumentParser(description="Train resnet50 cifar10")
    parser.add_argument("--batch_size", type=int, default=256)
    parser.add_argument("--epoch", type=int, default=50)
    parser.add_argument("--data_augmentation", type=bool, default=False)
    parser.add_argument("--model_dir", type=str, default="./model_keras_resnet")
    parser.add_argument("--enable_bottleneck", type=bool, default=True)
    args = parser.parse_args()

    mirrored_strategy = tf.distribute.MirroredStrategy()

    with mirrored_strategy.scope():
        model = ResNet50(weights=None, input_shape=(32, 32, 3), classes=10)
        opt = tf.keras.optimizers.Adam(learning_rate=0.001)
        model.compile(loss="categorical_crossentropy", optimizer=opt, metrics=["accuracy"])

    # start the training.
    train(args.batch_size, args.epoch, model, args.enable_bottleneck, args.data_augmentation)


if __name__ == "__main__":
    main()
