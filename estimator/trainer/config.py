train_batch_size = 64
n_epochs = 100
steps_to_train = None
shuffle_buffer_size = 2000
export_path = None
n_eval_games = 100
n_games = 400
n_mcts_sim = 200
c_puct = 4.0
temperature = [1, 0.001]
temperature_scheduler = 30
eta = 0.03
epsilon = 0.25
learning_rates = [0.01, 0.001, 0.0001]
learning_rates_scheduler = [400000, 600000]
momentum_rate = 0.9
n_res_blocks = 5
l2_regularization = 0.0001
pol_conv_width = 2
val_conv_width = 1
conv_width = 256
fc_width = 256
summary_steps = 256
keep_checkpoint_max = 5
mean_square_weight = 1
n_rows = 9
n_cols = 9
history = 8
win_ratio = 55
use_random_symmetry = True
job_dir = "model"
summary_step = 256
main_data_dir = None
weight_dir = None
selfplay_dir = None
holdout_dir = None
holdout_pct = 0.05
sgf_dir = None
verbosity = "INFO"
