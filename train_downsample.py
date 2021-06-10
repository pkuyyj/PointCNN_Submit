import argparse
import numpy as np
import tensorflow as tf
import socket

import os
import sys

os.environ['TF_CPP_MIN_LOG_LEVEL']='2'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.append(BASE_DIR)
sys.path.append(ROOT_DIR)
sys.path.append(os.path.join(ROOT_DIR, 'utils'))
import provider
from model import *
import sample_x

# 基本环境配置
parser = argparse.ArgumentParser()
parser.add_argument('--gpu', type=int, default=0, help='GPU to use [default: GPU 0]')
parser.add_argument('--log_dir', default='log_downsample', help='Log dir [default: log]')
parser.add_argument('--num_point', type=int, default=8192, help='Point number [default: 65536]')
parser.add_argument('--max_epoch', type=int, default=1, help='Epoch to run [default: 2000]')
parser.add_argument('--batch_size', type=int, default=1, help='Batch Size during training [default: 1]')
parser.add_argument('--learning_rate', type=float, default=0.001, help='Initial learning rate [default: 0.001]')
parser.add_argument('--momentum', type=float, default=0.9, help='Initial learning rate [default: 0.9]')
parser.add_argument('--optimizer', default='adam', help='adam or momentum [default: adam]')
parser.add_argument('--decay_step', type=int, default=300000, help='Decay step for lr decay [default: 300000]')
parser.add_argument('--decay_rate', type=float, default=0.5, help='Decay rate for lr decay [default: 0.5]')
parser.add_argument('--test_area', type=int, default=6, help='Which area to use for test, option: 1-6 [default: 6]')
FLAGS = parser.parse_args()

BATCH_SIZE = FLAGS.batch_size
NUM_POINT = FLAGS.num_point
MAX_EPOCH = FLAGS.max_epoch
NUM_POINT = FLAGS.num_point
BASE_LEARNING_RATE = FLAGS.learning_rate
GPU_INDEX = FLAGS.gpu
MOMENTUM = FLAGS.momentum
OPTIMIZER = FLAGS.optimizer
DECAY_STEP = FLAGS.decay_step
DECAY_RATE = FLAGS.decay_rate

LOG_DIR = FLAGS.log_dir
if not os.path.exists(LOG_DIR): os.mkdir(LOG_DIR)
os.system('cp model.py %s' % (LOG_DIR))  # bkp of model def
os.system('cp train.py %s' % (LOG_DIR))  # bkp of train procedure
LOG_FOUT = open(os.path.join(LOG_DIR, 'log_train.txt'), 'w')
LOG_FOUT.write(str(FLAGS) + '\n')

#基本参数
MAX_NUM_POINT = 8192
NUM_CLASSES = 23

BN_INIT_DECAY = 0.5
BN_DECAY_DECAY_RATE = 0.5
# BN_DECAY_DECAY_STEP = float(DECAY_STEP * 2)
BN_DECAY_DECAY_STEP = float(DECAY_STEP)
BN_DECAY_CLIP = 0.99

#HOSTNAME = socket.gethostname()

#dataset路径 对应要做修改 SemanticPOSS_dataset\dataset
dataset_path = '/home/CORP.PKUSC.ORG/pkuyyj/PointCNN.Pytorch/data/data_poss'

#注意第一次运行的时候要init
provider.init_dataset(dataset_path)

data_batch_list = []
label_batch_list = []

print("begin2")
#训练时用前五个sequences
for i in range(5):
    data_,label_ = provider.load_one_sequence(dataset_path,i)
    data_batch_list.append(data_)
    label_batch_list.append(label_)
print("begin1")
data_batches_1 = np.concatenate(data_batch_list, 0)
label_batches_1 = np.concatenate(label_batch_list, 0)

print("begin")
# down sample data in the first run:
# data_batches, label_batches = sample_x.sample_x_distance(data_batches_1, label_batches_1, 1, MAX_NUM_POINT)
data_batches = np.load(file="sample_try_data_2.npy", allow_pickle= True)
label_batches = np.load(file="sample_try_label_2.npy", allow_pickle= True)
print(data_batches.shape)
print(label_batches.shape)

print("load_data_completed")

#此处做训练集与测试集划分 用最简单的随机方法 可以在后续做修改 划分比例为5:1
data_index = np.arange(data_batches.shape[0])
np.random.shuffle(data_index)
print(data_index)
train_size = int(5*data_index.shape[0]/6)
train_idxs = data_index[:train_size]
test_idxs = data_index[train_size:]

# 划分测试集与训练集
train_data = data_batches[train_idxs, ...]
train_label = label_batches[train_idxs]
test_data = data_batches[test_idxs, ...]
test_label = label_batches[test_idxs]
print(train_data.shape, train_label.shape)
print(test_data.shape, test_label.shape)

#第一种shuffle
train_shape_0 = train_data.shape[0]
train_shape_1 = train_data.shape[1]
test_shape_0 = test_data.shape[0]
test_shape_1 = test_data.shape[1]
train_random_shape_1 = np.arange(train_shape_1)
test_random_shape_1 = np.arange(test_shape_1)

#第一种shuffle，每个图分别Shuffle 即点的排布都不相同
for i in range(train_shape_0):
    np.random.shuffle(train_random_shape_1)
    train_data[i] = train_data[i,train_random_shape_1]
    train_label[i] = train_label[i,train_random_shape_1]
    np.random.shuffle(test_random_shape_1)
    test_data[i] = test_data[i,test_random_shape_1]
    test_label[i] = test_label[i,test_random_shape_1]
#第二种shuffle

print("The training begins")

# 写记录的函数的
def log_string(out_str):
    LOG_FOUT.write(out_str + '\n')
    LOG_FOUT.flush()
    print(out_str)


def get_learning_rate(batch):
    learning_rate = tf.train.exponential_decay(
        BASE_LEARNING_RATE,  # Base learning rate.
        batch * BATCH_SIZE,  # Current index into the dataset.
        DECAY_STEP,  # Decay step.
        DECAY_RATE,  # Decay rate.
        staircase=True)
    learning_rate = tf.maximum(learning_rate, 0.00001)  # CLIP THE LEARNING RATE!!
    return learning_rate


def get_bn_decay(batch):
    bn_momentum = tf.train.exponential_decay(
        BN_INIT_DECAY,
        batch * BATCH_SIZE,
        BN_DECAY_DECAY_STEP,
        BN_DECAY_DECAY_RATE,
        staircase=True)
    bn_decay = tf.minimum(BN_DECAY_CLIP, 1 - bn_momentum)
    return bn_decay


def train():
    with tf.Graph().as_default():
        with tf.device('/gpu:' + str(GPU_INDEX)):

            # import model
            pointclouds_pl, labels_pl = placeholder_inputs(BATCH_SIZE, NUM_POINT)

            is_training_pl = tf.placeholder(tf.bool, shape=())

            # Note the global_step=batch parameter to minimize.
            # That tells the optimizer to helpfully increment the 'batch' parameter for you every time it trains.
            batch = tf.Variable(0)
            bn_decay = get_bn_decay(batch)
            tf.summary.scalar('bn_decay', bn_decay)

            # Get model and loss

            # import model
            # 从model里读取net和loss函数
            pred, end_point = get_model(pointclouds_pl, is_training_pl, bn_decay=bn_decay)
            loss = get_loss(pred, labels_pl, end_point)

            tf.summary.scalar('loss', loss)

            correct = tf.equal(tf.argmax(pred, 2), tf.to_int64(labels_pl))
            accuracy = tf.reduce_sum(tf.cast(correct, tf.float32)) / float(BATCH_SIZE * NUM_POINT)
            tf.summary.scalar('accuracy', accuracy)

            # Get training operator
            learning_rate = get_learning_rate(batch)
            tf.summary.scalar('learning_rate', learning_rate)
            if OPTIMIZER == 'momentum':
                optimizer = tf.train.MomentumOptimizer(learning_rate, momentum=MOMENTUM)
            elif OPTIMIZER == 'adam':
                optimizer = tf.train.AdamOptimizer(learning_rate)
            train_op = optimizer.minimize(loss, global_step=batch)

            # Add ops to save and restore all the variables.
            saver = tf.train.Saver()

        # Create a session
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        config.allow_soft_placement = True
        config.log_device_placement = True
        sess = tf.Session(config=config)

        # Add summary writers
        merged = tf.summary.merge_all()
        train_writer = tf.summary.FileWriter(os.path.join(LOG_DIR, 'train'),
                                             sess.graph)
        test_writer = tf.summary.FileWriter(os.path.join(LOG_DIR, 'test'))

        # Init variables
        init = tf.global_variables_initializer()
        sess.run(init, {is_training_pl: True})

        ops = {'pointclouds_pl': pointclouds_pl,
               'labels_pl': labels_pl,
               'is_training_pl': is_training_pl,
               'pred': pred,
               'loss': loss,
               'train_op': train_op,
               'merged': merged,
               'step': batch}

        for epoch in range(MAX_EPOCH):
            log_string('**** EPOCH %03d ****' % (epoch))
            sys.stdout.flush()

            train_one_epoch(sess, ops, train_writer)
            eval_one_epoch(sess, ops, test_writer)

            # Save the variables to disk.
            if epoch % 1 == 0:
                save_path = saver.save(sess, os.path.join(LOG_DIR, "model.ckpt"))
                log_string("Model saved in file: %s" % save_path)

def shuffle_data(data, labels):
    idx = np.arange(len(labels))
    np.random.shuffle(idx)
    return data[idx, ...], labels[idx], idx


def train_one_epoch(sess, ops, train_writer):
    """ ops: dict mapping from string to tf ops """
    is_training = True

    log_string('----')
    
    current_data, current_label, _ = shuffle_data(train_data[:, 0:NUM_POINT, :], train_label)

    file_size = current_data.shape[0]
    num_batches = file_size // BATCH_SIZE
    #num_batches = 1

    #加了每一个类的结果
    total_seen_class = [0 for _ in range(NUM_CLASSES)]
    total_correct_class = [0 for _ in range(NUM_CLASSES)]

    total_correct = 0
    total_seen = 0
    loss_sum = 0

    # 每次为batch_size投喂参数
    for batch_idx in range(num_batches):
        #if batch_idx % 100 == 0:
        print('Current batch/total batch num: %d/%d' % (batch_idx, num_batches))
        start_idx = batch_idx * BATCH_SIZE
        end_idx = (batch_idx + 1) * BATCH_SIZE

        feed_dict = {ops['pointclouds_pl']: current_data[start_idx:end_idx, :, :],
                     ops['labels_pl']: current_label[start_idx:end_idx],
                     ops['is_training_pl']: is_training, }

        summary, step, _, loss_val, pred_val = sess.run(
            [ops['merged'], ops['step'], ops['train_op'], ops['loss'], ops['pred']],
            feed_dict=feed_dict)
        train_writer.add_summary(summary, step)
        pred_val = np.argmax(pred_val, 2)
        correct = np.sum(pred_val == current_label[start_idx:end_idx])
        total_correct += correct
        total_seen += (BATCH_SIZE * NUM_POINT)
        loss_sum += loss_val

        #看每一类的结果
        for i in range(start_idx, end_idx):
            for j in range(NUM_POINT):
                l = current_label[i, j]
                total_seen_class[l] += 1
                total_correct_class[l] += (pred_val[i - start_idx, j] == l)

    log_string('mean loss: %f' % (loss_sum / float(num_batches)))
    log_string('accuracy: %f' % (total_correct / float(total_seen)))

    #看每一个类的结果
    log_string('eval mean loss: %f' % (loss_sum / float(total_seen / NUM_POINT)))
    log_string('eval accuracy: %f' % (total_correct / float(total_seen)))
    log_string('eval avg class acc: %f' % (
        np.mean(np.array(total_correct_class) / np.array(total_seen_class, dtype=np.float))))
    for t in range(22):
        if total_seen_class[t] != 0:
            log_string('Class %d ' % t)
            log_string('acc: %f' % (total_correct_class[t] / total_seen_class[t]))

def eval_one_epoch(sess, ops, test_writer):
    """ ops: dict mapping from string to tf ops """
    is_training = False
    total_correct = 0
    total_seen = 0
    loss_sum = 0
    total_seen_class = [0 for _ in range(NUM_CLASSES)]
    total_correct_class = [0 for _ in range(NUM_CLASSES)]

    log_string('----')
    # 测试过程 current_data为测试集
    current_data = test_data[:, 0:NUM_POINT, :]
    current_label = np.squeeze(test_label)

    file_size = current_data.shape[0]
    num_batches = file_size // BATCH_SIZE

    for batch_idx in range(num_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = (batch_idx + 1) * BATCH_SIZE

        feed_dict = {ops['pointclouds_pl']: current_data[start_idx:end_idx, :, :],
                     ops['labels_pl']: current_label[start_idx:end_idx],
                     ops['is_training_pl']: is_training}
        summary, step, loss_val, pred_val = sess.run([ops['merged'], ops['step'], ops['loss'], ops['pred']],
                                                     feed_dict=feed_dict)
        test_writer.add_summary(summary, step)
        pred_val = np.argmax(pred_val, 2)
        correct = np.sum(pred_val == current_label[start_idx:end_idx])
        total_correct += correct
        total_seen += (BATCH_SIZE * NUM_POINT)
        loss_sum += (loss_val * BATCH_SIZE)

        #看看能不能输出每一个类的正确率
        for i in range(start_idx, end_idx):
            for j in range(NUM_POINT):
                l = current_label[i, j]
                total_seen_class[l] += 1
                total_correct_class[l] += (pred_val[i - start_idx, j] == l)

    log_string('eval mean loss: %f' % (loss_sum / float(total_seen / NUM_POINT)))
    log_string('eval accuracy: %f' % (total_correct / float(total_seen)))
    log_string('eval avg class acc: %f' % (
        np.mean(np.array(total_correct_class) / np.array(total_seen_class, dtype=np.float))))
    for t in range(22):
        if total_seen_class[t] != 0:
            log_string('Class %d ' % t)
            log_string('acc: %f' % (total_correct_class[t] / total_seen_class[t]))

if __name__ == "__main__":
    train()
    LOG_FOUT.close()