import numpy as np
import sys
import six
import pachi_py

from copy import deepcopy

# TODO: change for a variable using parser for HISTORY
HISTORY = 8

# The coordinate representation of Pachi (and pachi_py) is defined on a board
# with extra rows and columns on the margin of the board, so positions on the board
# are not numbers in [0, board_size**2) as one would expect. For this Go env, we instead
# use an action representation that does fall in this more natural range.
def _pass_action(board_size):
    """ Return the pass action """
    return board_size ** 2


def _resign_action(board_size):
    """ Return the resign action """
    return board_size ** 2 + 1


def _coord_to_action(board, c):
    """ Converts Pachi coordinates to actions """
    if c == pachi_py.PASS_COORD:
        return _pass_action(board.size)

    if c == pachi_py.RESIGN_COORD:
        return _resign_action(board.size)

    i, j = board.coord_to_ij(c)
    return i * board.size + j


def _action_to_coord(board, a):
    """ Converts actions to Pachi coordinates """
    if a == _pass_action(board.size):
        return pachi_py.PASS_COORD

    if a == _resign_action(board.size):
        return pachi_py.RESIGN_COORD

    return board.ij_to_coord(a // board.size, a % board.size)


def _format_state(history, player_color, board_size):
    """ Format the board to be used as the input to the NN.
        See Neural network architecture p.8 of the paper 
    Args:
        history (np.array): current state + 7 previous states for the 2 players.
        `history` is then a np.array of dimension (16, board_size, board_size)
        player_color (int): color of the current player (1 if black, 2 if white)
        board_size (int): game board side size
    Returns:
        np.array: Tensor of dimension (17, board_size, board_size) that is formated
        according to the description under `Neural network architecture` page 8 of
        the paper
    """
    color_to_play = np.full((board_size, board_size, 1), player_color - 1)
    final_state = np.concatenate((history, color_to_play), axis=-1)
    return final_state


class GoGame():
    """ Go environment. Play against a fixed opponent """

    def __init__(self, player_color='black', board_size=9):
        """
        Args:
            player_color (str): Stone color for the agent. Either 'black' or 'white'
            board_size (int): board game side size
        """
        self.board_size = board_size

        colormap = {
            'black': pachi_py.BLACK,  # pachi_py.BLACK = 1
            'white': pachi_py.WHITE,  # pachi_py.WHITE = 2
        }
        self.player_color = colormap[player_color]
        self.reset()

    def __deepcopy__(self, memo):
        """ Clone the current instance of the game """
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "board":
                setattr(result, k, self.board.clone())
            else:
                setattr(result, k, deepcopy(v, memo))
        return result

    def play_action(self, action):
        """ If 2 player passes the game end (rule of Go),
            `play_action` performs an action and update
            the state of the game
        Args:
            action (int): move to execute
        Attributes:
            done (bool): Whether the game ends or not
            state (np.array): Tensor of size (16, board_size, board_size) as
            described in the paper under `Neural network architecture` page 8
            (the last layer is added in _format_state)
        """

        if not self.done:
            try:
                self._act(action)
            except pachi_py.IllegalMove:
                six.reraise(*sys.exc_info())

        self.done = self.board.is_terminal
        self.state = _format_state(self.history, self.player_color, self.board_size)

        return self.state, self.done

    def _komi(self):
        """ Add komi (bonus point) to the second player
            according to the size of the game in order to
            balance the game
        """
        if 14 <= self.board_size <= 19:
            return 7.5
        elif 9 <= self.board_size <= 13:
            return 5.5
        return 0

    def reset(self):
        """ reset the Game
        Attributes:
            komi (int): komi value (bonus point) to balance the game
            board (PachiBoardPtr): board class with associate methods
            done (bool): Wether the game ends or not
            state (np.array): Tensor of size (16, board_size, board_size)
            formatted as described in the paper under `Neural network architecture` 
            page 8 (the last layer is added in _format_state)
        """
        self.komi = self._komi()
        self.board = pachi_py.CreateBoard(self.board_size)  # object with method
        self.done = False

        self.history = np.zeros((self.board_size, self.board_size, HISTORY * 2), dtype=np.int8)
        self.state = np.zeros((self.board_size, self.board_size, HISTORY * 2 + 1), dtype=np.int8)

        return self.state

    def get_legal_actions(self):
        """ Get all the legal actions and transform their coords into integer values
        Returns:
            np.array: array of integers that represents the legal actions.
        """

        legal_moves = self.board.get_legal_coords(self.player_color, filter_suicides=True)
        return np.array([_coord_to_action(self.board, pachi_move) for pachi_move in legal_moves])

    def _act(self, action):
        """ Executes an action for the current player 
        Args:
            action (int): action to execute
        Attributes:
            board (PachiBoardPtr): update the board instance
            player_color (int): Switch player
        """

        self.board = self.board.play(_action_to_coord(self.board, action), self.player_color)

        board = self.board.encode()
        color = self.player_color - 1

        # discard last state of the opponent player and add move of the current player to the state
        self.history = np.roll(self.history, 1, axis=-1)
        self.history[:, :, 0] = np.array(board[color])

        # switch player
        self.player_color = pachi_py.stone_other(self.player_color)

    def get_reward(self):
        """ Get the winner using Tromp-Taylor scoring """

        # Tromp-Taylor scoring https://github.com/openai/pachi-py/blob/master/pachi_py/pachi/board.c#L1556
        # is called by: https://github.com/openai/pachi-py/blob/master/pachi_py/goutil.cpp#L81
        # which is called by the python API: https://github.com/openai/pachi-py/blob/master/pachi_py/cypachi.pyx#L52
        # Note: we don't have access to the komi variable through the pachi_py API, so we need to add it ourself
        score = self.komi + self.board.official_score
        white_wins = score > 0
        black_wins = score < 0

        # TODO: isn't it maybe white_wins and self.player_color = BLACK (because we have changed the color
        #  just after white had played?)
        player_wins = (white_wins and self.player_color == pachi_py.WHITE) \
                      or (black_wins and self.player_color == pachi_py.BLACK)

        # TODO: replace by white_wins ^ black_wins
        reward = 1 if player_wins else -1 if (white_wins ^ black_wins) else 0

        return reward

    def get_result_string(self):
        """ Get the result as a SGF formatted string.
            For example: "B+W" means Black wins by resign
                         "B+3.5" means Black wins by 3.5 points
        """
        score = self.komi + self.board.official_score
        players = {
            True: "W",
            False: "B"
        }
        winner = players[score > 0]

        # TODO: handle TIES
        if score == 0:
            return winner + "+" + players[not(score > 0)]

        return winner + "+" + str(abs(score))

    def get_states(self):
        return self.state.copy()

    def render(self):
        """ Render the board in the console """
        outfile = sys.stdout
        outfile.write('To play: {}\n{}\n'.format(six.u(
                        pachi_py.color_to_str(self.player_color)),
                        self.board.__repr__().decode()))
        return outfile
