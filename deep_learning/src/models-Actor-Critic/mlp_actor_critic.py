#! usr/bin/env python
import pandas as pd
import numpy as np
from py_geohash_any import geohash as gh
import datetime
import random
import numpy as np
from collections import deque
import time
from keras.layers.normalization import BatchNormalization
import json
from IPython.display import SVG
from collections import defaultdict
from keras.models import model_from_json
from keras.models import Sequential
from keras.layers import LSTM
from keras.layers import InputLayer
from keras.layers.core import Dense, Dropout, Activation, Flatten
from keras.optimizers import SGD , Adam
import tensorflow as tf
import pickle
from operator import itemgetter
import sys
sys.path.insert(0, '../data/') ## for running on local
import auxiliary_functions, make_dataset
from auxiliary_functions import convert_miles_to_minutes_nyc, list_of_output_predictions_to_direction
__author__= ' Jonathan Hilgart'



class ActorCriticNYCMLP(object):

    """Train an actor critic model to maximize revenue. for a NYC taxi driver.\
    Code inspired from http://www.rage.net/~greg/2016-07-05-ActorCritic-with-OpenAI-Gym.htmlCode """

    def __init__(self, args, ACTION_SPACE, OBSERVATION_SPACE,
                 list_of_unique_geohashes,list_of_time_index, list_of_geohash_index,
                             list_of_inverse_heohash_index, final_data_structure, ):

        self.ACTION_SPACE = ACTION_SPACE
        self.OBSERVATION_SPACE = OBSERVATION_SPACE
        self.args = args
        self.actor_model()
        self.critic_model()
        self.list_of_unique_geohashes = list_of_unique_geohashes
        self.list_of_time_index = list_of_time_index
        self.list_of_geohash_index = list_of_geohash_index
        self.list_of_inverse_heohash_index = list_of_inverse_heohash_index
        self.final_data_structure = final_data_structure


    def actor_model(self):
        """Build an actor model with mlp.
         http://www.rage.net/~greg/2016-07-05-ActorCritic-with-OpenAI-Gym.htmlCode """
        model_mlp = Sequential()
        model_mlp.add(Dense(100, input_shape=(self.OBSERVATION_SPACE,)))
        model_mlp.add(BatchNormalization())
        model_mlp.add(Activation('relu'))
        model_mlp.add(Dropout(.3))
        model_mlp.add(Dense(500))
        model_mlp.add(BatchNormalization())
        model_mlp.add(Activation('relu'))
        model_mlp.add(Dropout(.3))
        model_mlp.add(Dense(1000))
        model_mlp.add(BatchNormalization())
        model_mlp.add(Activation('relu'))
        model_mlp.add(Dropout(.3))
        model_mlp.add(Dense(self.ACTION_SPACE, activation='linear'))
        # predict which geohash to move to next
        adam = Adam(clipnorm=1.0)
        model_mlp.compile(loss='mse',optimizer=adam)
        self.actor_model = model_mlp


    def critic_model(self):
        """Build a critic model.
        Code inspired from http://www.rage.net/~greg/2016-07-05-ActorCritic-with-OpenAI-Gym.html"""
        model_mlp = Sequential()
        model_mlp.add(Dense(100, input_shape=(self.OBSERVATION_SPACE,)))
        model_mlp.add(BatchNormalization())
        model_mlp.add(Activation('relu'))
        model_mlp.add(Dropout(.3))
        model_mlp.add(Dense(500))
        model_mlp.add(BatchNormalization())
        model_mlp.add(Activation('relu'))
        model_mlp.add(Dropout(.3))
        model_mlp.add(Dense(1000))
        model_mlp.add(BatchNormalization())
        model_mlp.add(Activation('relu'))
        model_mlp.add(Dropout(.3))
        model_mlp.add(Dense(1, activation='linear'))  # predict the value
        adam = Adam(clipnorm=1.0)
        model_mlp.compile(loss='mse', optimizer=adam)
        self.critic_model = model_mlp

    def NaiveApproach(self, s_time_, s_geohash_,starting_geo, input_fare_list = None,
                      historic_current_fare = None):
        """Assign the same probability to every state and
        keep track of the total fare received, total fare over time,
        and geohashes visited"""

        ## parameters to track where we are and at what time
        starting_geohash = starting_geo
        s_time = s_time_
        s_geohash = s_geohash_
        list_of_geohashes_visited = []

        ## check and see if we have old fare to continue adding to
        if input_fare_list == None:
            total_fare = 0
            total_fare_over_time = []

        else:
            total_fare = historic_current_fare
            total_fare_over_time = input_fare_list


        while True:
            a_t = np.zeros([self.ACTION_SPACE])
            action_index = random.randrange(self.ACTION_SPACE)
            a_t[action_index] = 1
            #Get the neighbors from the current geohash - convert back to string
            current_geohash_string = self.list_of_inverse_heohash_index[s_geohash]
            neighbors = gh.neighbors(current_geohash_string)
            # Get the direction we should go
            direction_to_move_to = list_of_output_predictions_to_direction[action_index]
            # Get the geohash of the direction we moved to
            if direction_to_move_to =='stay':
                new_geohash = starting_geohash  # stay in current geohash, get the index of said geohash
                possible_rewards = np.array(self.final_data_structure[s_time][new_geohash])
                # hash with the letters  of the geohash above
                new_geohash = self.list_of_geohash_index[starting_geohash]
            else:
                new_geohash = neighbors[direction_to_move_to]## give us the geohash to move to next

            # get the reward of the geohash we just moved to (this is the ratio of fare /time of trip)
            # time, geohash, list of tuple ( fare, time ,ratio)
            possible_rewards = np.array(self.final_data_structure[s_time][new_geohash])

            if len (possible_rewards) ==0:
                r_t = -.1  # we do not have information for this time and geohash, don't go here. waste gass
                fare_t = 0  # no information so the fare = 0
                s_time1 = s_time+10  # assume this took ten minutes
            else:
                reward_option = np.random.randint(0,len(possible_rewards))
                r_t =  possible_rewards[reward_option][2]  # get the ratio of fare / trip time
                fare_t = possible_rewards[reward_option][0]
                # get the trip length
                s_time1 = s_time + possible_rewards[reward_option][1]
            s_geohash1 = self.list_of_geohash_index[new_geohash]
            # store the transition in D
            if s_time1 <= 2350: # The last possible time for a trip
                terminal = 0
                 #get the naive implementation per day
            else:  # the day is over, pick a new starting geohash and time
                break  # the day is over


            total_fare += fare_t
            total_fare_over_time.append(total_fare)
            list_of_geohashes_visited.append(starting_geohash)
            # increment the state and time information
            s_time = s_time1
            s_geohash = s_geohash1
            starting_geohash = new_geohash## update the starting geohash in case we stay here
        return total_fare, total_fare_over_time, list_of_geohashes_visited


    def trainer(self, n_days=10, batchSize=64,
                gamma=0.975, epsilon=1, min_epsilon=0.1, save_model=True,
                buffer=10000):
        """Train a Actor Critic model for a given number of days.
        Code inspired from http://www.rage.net/~greg/2016-07-05-ActorCritic-with-OpenAI-Gym.html
        Returns actor_loss,critic_loss, total_fare_over_time, daily_fare
        """

        # Replay buffers
        actor_replay = []
        critic_replay = []
        # Track loss over time
        actor_loss = []
        critic_loss = []
        total_fare = 0
        total_fare_over_time = []
        average_fare_per_day = []
        percent_profitable_moves_over_time = []
        ACTIONS = 9
        total_days_driven = 0
        day_start = time.time()
        # naive implementation results
        total_naive_fare = 0
        total_naive_fare_over_time = []
        list_of_naive_geohashes_visited = []
        naive_geohashes_visited = []


        for i in range(n_days):
            wins = 0
            losses = 0
            daily_fare = 0

            done = False
            reward = 0
            info = None
            move_counter = 0
            starting_geohash = np.random.choice(list_of_unique_geohashes)
            s_time = np.random.choice(list_of_time_index)
            s_geohash = list_of_geohash_index[starting_geohash]
            a_t = np.zeros([ACTIONS])
            ## start the naive appraoch
            total_naive_fare, total_naive_fare_over_time,\
             naive_geohashes_visited = \
            self.NaiveApproach(s_time, s_geohash,
                starting_geohash, total_naive_fare_over_time, total_naive_fare)

            orig_state = np.array([[s_time, s_geohash]])
            orig_reward = 0
            move_counter = 0

            while(not done):
                # Get original state, original reward, and critic's value for this state.

                orig_reward = reward
                orig_val = self.critic_model.predict(orig_state)

                if (random.random() < epsilon): #choose random action
                    print('----------We took a random action ----------')
                    action = np.random.randint(0,ACTIONS)
                else: #choose best action from Q(s,a) values
                    qval = self.actor_model.predict(orig_state)
                    action = np.argmax(qval)

                # take action and observe the reward

                #Get the neighbors from the current geohash - convert back to string
                current_geohash_string = list_of_inverse_heohash_index[s_geohash]
                neighbors = gh.neighbors(current_geohash_string)
                # Get the direction we should go
                direction_to_move_to = list_of_output_predictions_to_direction[action]
                # Get the geohash of the direction we moved to
                if direction_to_move_to =='stay':
                    new_geohash = starting_geohash # stay in current geohash, get the index of said geohash
                    possible_rewards = np.array(final_data_structure[s_time][new_geohash])
                    # hash with the letters  of the geohash above
                    new_geohash = list_of_geohash_index[starting_geohash]
                else:
                    new_geohash = neighbors[direction_to_move_to]## give us the geohash to move to next

                # get the reward of the geohash we just moved to (this is the ratio of fare /time of trip)
                # time, geohash, list of tuple ( fare, time ,ratio)
                possible_rewards = np.array(final_data_structure[s_time][new_geohash])

                if len (possible_rewards) ==0:
                    r_t = -.1  # we do not have information for this time and geohash, don't go here. waste gass
                    fare_t = 0  # no information so the fare = 0
                    s_time1 = s_time+10  # assume this took ten minutes
                else:
                    reward_option = np.random.randint(0, len(possible_rewards))
                    r_t = possible_rewards[reward_option][2] # get the ratio of fare / trip time
                    fare_t = possible_rewards[reward_option][0]
                    # get the trip length
                    s_time1 = s_time + possible_rewards[reward_option][1]
                s_geohash1 = list_of_geohash_index[new_geohash]

                # get the new state that we moved to
                new_state = np.array([[s_time1, s_geohash1]])
                # Append the fare of the new state
                total_fare += fare_t
                daily_fare += fare_t
                total_fare_over_time.append(total_fare)

                # Critic's value for this new state.
                new_val = self.critic_model.predict(new_state)

                # See if we finished a day
                if s_time1 <= 2350:  # The last possible time for a tripn
                    terminal = 0
                else: # the day is over, pick a new starting geohash and time
                    print('ONE DAY OVER!')
                    done = True
                    total_days_driven += 1


                if not done: # Non-terminal state.
                    target = orig_reward + (gamma * new_val)
                else:
                    # In terminal states, the environment tells us
                    # the value directly.
                    target = orig_reward + (gamma * r_t)

                # For our critic, we select the best/highest value.. The
                # value for this state is based on if the agent selected
                # the best possible moves from this state forward.
                #
                # BTW, we discount an original value provided by the
                # value network, to handle cases where its spitting
                # out unreasonably high values.. naturally decaying
                # these values to something reasonable.
                best_val = max((orig_val*gamma), target)
                # Now append this to our critic replay buffer.
                critic_replay.append([orig_state, best_val])


                # Build the update for the Actor. The actor is updated
                # by using the difference of the value the critic
                # placed on the old state vs. the value the critic
                # places on the new state.. encouraging the actor
                # to move into more valuable states.
                actor_delta = new_val - orig_val
                actor_replay.append([orig_state, action, actor_delta])

                # Critic Replays...
                while(len(critic_replay) > buffer): # Trim replay buffer
                    critic_replay.pop(0)
                # Start training when we have enough samples.
                if(len(critic_replay) >= buffer):
                    minibatch = random.sample(critic_replay, batchSize)
                    X_train = []
                    y_train = []
                    for memory in minibatch:
                        m_state, m_value = memory
                        y = np.empty([1])
                        y[0] = m_value
                        X_train.append(m_state)
                        y_train.append(y.reshape((1,)))
                    X_train = np.vstack(X_train)
                    y_train = np.vstack(y_train)
                    loss = self.critic_model.train_on_batch(X_train, y_train)
                    critic_loss.append(loss)

                # Actor Replays...
                while(len(actor_replay) > buffer):
                    actor_replay.pop(0)
                if(len(actor_replay) >= buffer):
                    X_train = []
                    y_train = []
                    minibatch = random.sample(actor_replay, batchSize)
                    for memory in minibatch:
                        m_orig_state, m_action, m_value = memory
                        old_qval = self.actor_model.predict(m_orig_state)
                        y = np.zeros(( 1, ACTIONS))
                        y[:] = old_qval[:]
                        y[0][m_action] = m_value
                        X_train.append(m_orig_state)
                        y_train.append(y)
                    X_train = np.vstack(X_train)
                    y_train = np.vstack(y_train)
                    loss = self.actor_model.train_on_batch(X_train, y_train)
                    actor_loss.append(loss)

                # Bookkeeping at the end of the turn.

                if r_t > 0 :  # Win
                    wins += 1
                else:  # Loss
                    losses += 1

                # increment the state and time information
                s_time = s_time1
                s_geohash = s_geohash1
    #             if return_metrics == True:
    #                 list_of_geohashes_visited.append(starting_geohash)
                orig_state = new_state
                starting_geohash = new_geohash  # update the starting geohash in case we stay here

            # Finised Day

            if save_model == True:
                if n_days % 10 == 0:  # save every ten training days
                    print("Now we save model")
                    self.actor_model.save_weights(self.args['save_model_weights_actor'],
                                                  overwrite=True)
                    self.critic_model.save_weights(self.args['save_model_weights_critic'],
                                                   overwrite=True)

                    with open("model_actor.json", "w") as outfile:
                        json.dump(self.actor_model.to_json(), outfile)
                    with open("model_critic.json", "w") as outfile:
                        json.dump(self.critic_model.to_json(), outfile)

            average_fare_per_day.append(daily_fare/(wins+losses))
            percent_profitable_moves_over_time.append(wins/(wins+losses))
            day_end_time = time.time()
            print('---------METRICS----------')
            print("Day #: %s" % (i+1,))
            print("Moves this round %s" % move_counter)
            print("Wins/Losses %s/%s" % (wins, losses))
            print('Percent of moves this day that were profitable {}'.format(wins/(wins+losses)))
            print('Epsilon is {}'.format(epsilon))
            print('This day took {}'.format(day_end_time - day_start))
            print('Critic last loss  = {}'.format(critic_loss[-1:]))
            print('Actor last loss = {}'.format(actor_loss[-1:]))
            print("--------METIRCS END---------")

            day_start = day_end_time
            if epsilon > min_epsilon:
                epsilon -= (1/n_days)

        if save_model == True:
            print("FINISHED TRAINING!!")
            self.actor_model.save_weights(self.args['save_model_weights_actor'],
                                          overwrite=True)
            self.critic_model.save_weights(self.args['save_model_weights_critic'],
                                           overwrite=True)
            with open("model_actor.json", "w") as outfile:
                json.dump(self.actor_model.to_json(), outfile)
            with open("model_critic.json", "w") as outfile:
                json.dump(self.critic_model.to_json(), outfile)

            return actor_loss,critic_loss, total_fare_over_time, average_fare_per_day,\
                percent_profitable_moves_over_time, total_naive_fare_over_time
        else:
            return actor_loss,critic_loss, total_fare_over_time, average_fare_per_day,\
                percent_profitable_moves_over_time, total_naive_fare_over_time

def data_attributes(taxi_yellowcab_df):
    """Some random data objects needed to train the RL algorithm"""
    list_of_output_predictions_to_direction =\
        {0: 'nw', 1: 'n', 2: 'ne', 3: 'w', 4: 'stay', 5: 'e', 6: 'sw', 7: 's', 8: 'se'}
    list_of_unique_geohashes = taxi_yellowcab_df.geohash_pickup.unique()
    list_of_geohash_index = defaultdict(int)
    for idx, hash_n in enumerate(list_of_unique_geohashes):
        list_of_geohash_index[hash_n] = idx
    list_of_inverse_heohash_index = defaultdict(str)
    for idx, hash_n in enumerate(list_of_unique_geohashes):
        list_of_inverse_heohash_index[idx] = hash_n
    hours = [str(_) for _ in range(24)]
    minutes = [str(_) for _ in range(0, 60, 10)]
    minutes.append('00')
    list_of_time_index =[]
    for h in hours:
        for m in minutes:
            list_of_time_index.append(int(str(h)+str(m)))

    list_of_time_index = list(set(list_of_time_index))

    return list_of_output_predictions_to_direction, list_of_unique_geohashes, \
        list_of_geohash_index, list_of_time_index, list_of_inverse_heohash_index


if __name__ == '__main__':

    taxi_yellowcab_df, final_data_structure= make_dataset.main()
    ## the the data structures needed for the RL calss
    list_of_output_predictions_to_direction, list_of_unique_geohashes, \
        list_of_geohash_index, list_of_time_index, list_of_inverse_heohash_index\
         = data_attributes(taxi_yellowcab_df)

    args = {'mode':'Run','save_model':True,'model_weights_load':'model_mlp_linear.h5',
           'save_model_weights_critic':'mlp_critic.h5',
           'save_model_weights_actor':'mlp_actor.h5'}

    actor_critic_model = ActorCriticNYCMLP(args, 9, 2,
                                list_of_unique_geohashes, list_of_time_index,
                                list_of_geohash_index, list_of_inverse_heohash_index,
                                final_data_structure,buffer=5)
    # train our model
    actor_critic_model.trainer()


    #actor_loss,critic_loss, total_fare_over_time, average_fare_per_day,\
    #    percent_profitable_moves_over_time, total_naive_fare_over_time = \
    #    actor_critic_model.trainer()
