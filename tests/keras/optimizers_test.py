from __future__ import print_function
import pytest
import numpy as np
from numpy.testing import assert_allclose

from keras.utils import test_utils
from keras import optimizers, Input
from keras.models import Sequential, Model, load_model
from keras.layers.core import Dense, Activation, Lambda
from keras.utils.np_utils import to_categorical
from keras import backend as K
import tempfile


num_classes = 2


def get_test_data():
    np.random.seed(1337)
    (x_train, y_train), _ = test_utils.get_test_data(num_train=1000,
                                                     num_test=200,
                                                     input_shape=(10,),
                                                     classification=True,
                                                     num_classes=num_classes)
    y_train = to_categorical(y_train)
    return x_train, y_train


def _test_optimizer(optimizer, target=0.6):
    x_train, y_train = get_test_data()

    model = Sequential()
    model.add(Dense(10, input_shape=(x_train.shape[1],)))
    model.add(Activation('relu'))
    model.add(Dense(y_train.shape[1]))
    model.add(Activation('softmax'))
    model.compile(loss='categorical_crossentropy',
                  optimizer=optimizer,
                  metrics=['accuracy'])

    history = model.fit(x_train, y_train, epochs=3, batch_size=16, verbose=0)
    assert history.history['accuracy'][-1] >= target
    config = optimizers.serialize(optimizer)
    optim = optimizers.deserialize(config)
    new_config = optimizers.serialize(optim)
    new_config['class_name'] = new_config['class_name'].lower()
    assert sorted(config.keys()) == sorted(new_config.keys())
    # for k in config['config'].keys():
    #     assert config['config'][k] == new_config['config'][k]

    # Test constraints.
    model = Sequential()
    dense = Dense(10,
                  input_shape=(x_train.shape[1],),
                  kernel_constraint=lambda x: 0. * x + 1.,
                  bias_constraint=lambda x: 0. * x + 2.,)
    model.add(dense)
    model.add(Activation('relu'))
    model.add(Dense(y_train.shape[1]))
    model.add(Activation('softmax'))
    model.compile(loss='categorical_crossentropy',
                  optimizer=optimizer,
                  metrics=['accuracy'])
    model.train_on_batch(x_train[:10], y_train[:10])
    kernel, bias = dense.get_weights()
    assert_allclose(kernel, 1.)
    assert_allclose(bias, 2.)

    # Test saving.
    model = Sequential()
    model.add(Dense(1, input_dim=1))
    model.compile(loss='mse', optimizer=optimizer)
    model.fit(np.zeros((1, 1)), np.zeros((1, 1)))

    _, fname = tempfile.mkstemp('.h5')
    model.save(fname)
    model2 = load_model(fname)

    for w1, w2 in zip(model.get_weights(), model2.get_weights()):
        assert_allclose(w1, w2)


@pytest.mark.skipif((K.backend() != 'tensorflow'),
                    reason='Only Tensorflow raises a '
                           'ValueError if the gradient is null.')
def test_no_grad():
    inp = Input([3])
    x = Dense(10)(inp)
    x = Lambda(
        lambda l: 1.0 * K.reshape(K.cast(K.argmax(l), 'float32'), [-1, 1]),
        output_shape=lambda x: [x[0], 1])(x)
    mod = Model(inp, x)
    mod.compile('sgd', 'mse')
    with pytest.raises(ValueError):
        mod.fit(np.zeros([10, 3]), np.zeros([10, 1], np.float32),
                batch_size=10, epochs=10)


@pytest.mark.skipif((K.backend() == 'cntk'),
                    reason='Flaky with CNTK')
def test_sgd():
    sgd = optimizers.SGD(lr=0.01, momentum=0.9, nesterov=True)
    _test_optimizer(sgd)


def test_rmsprop():
    _test_optimizer(optimizers.RMSprop())
    _test_optimizer(optimizers.RMSprop(decay=1e-3))


def test_adagrad():
    _test_optimizer(optimizers.Adagrad(lr=1.))
    _test_optimizer(optimizers.Adagrad(lr=1., decay=1e-3))


def test_adadelta():
    _test_optimizer(optimizers.Adadelta(lr=1.), target=0.4)
    _test_optimizer(optimizers.Adadelta(lr=1., decay=1e-3), target=0.4)


def test_adam():
    _test_optimizer(optimizers.Adam())
    _test_optimizer(optimizers.Adam(decay=1e-3))


def test_adamax():
    _test_optimizer(optimizers.Adamax(lr=1.))
    _test_optimizer(optimizers.Adamax(lr=1., decay=1e-3))


def test_nadam():
    _test_optimizer(optimizers.Nadam())


def test_adam_amsgrad():
    _test_optimizer(optimizers.Adam(amsgrad=True))
    _test_optimizer(optimizers.Adam(amsgrad=True, decay=1e-3))


@pytest.mark.skipif((K.backend() == 'cntk'),
                    reason='Flaky with CNTK')
def test_clipnorm():
    sgd = optimizers.SGD(lr=0.01, momentum=0.9, clipnorm=0.5)
    _test_optimizer(sgd)


@pytest.mark.skipif((K.backend() == 'cntk'),
                    reason='Flaky with CNTK')
def test_clipvalue():
    sgd = optimizers.SGD(lr=0.01, momentum=0.9, clipvalue=0.5)
    _test_optimizer(sgd)


@pytest.mark.skipif((K.backend() != 'tensorflow'),
                    reason='Requires TensorFlow backend')
def test_tfoptimizer():
    from keras import constraints
    import tensorflow as tf
    if tf.__version__.startswith('1.'):
        optimizer = optimizers.TFOptimizer(tf.train.AdamOptimizer())
    else:
        optimizer = tf.keras.optimizers.Adam()

    model = Sequential()
    model.add(Dense(num_classes, input_shape=(3,),
                    kernel_constraint=constraints.MaxNorm(1)))
    model.compile(loss='mean_squared_error', optimizer=optimizer)
    model.fit(np.random.random((5, 3)), np.random.random((5, num_classes)),
              epochs=1, batch_size=5, verbose=0)

    if tf.__version__.startswith('1.'):
        with pytest.raises(NotImplementedError):
            optimizer.weights
        with pytest.raises(NotImplementedError):
            optimizer.get_config()
        with pytest.raises(NotImplementedError):
            optimizer.from_config(None)


if __name__ == '__main__':
    pytest.main([__file__])
