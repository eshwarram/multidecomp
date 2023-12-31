import pandas as pd
from utils import *
import numpy as np
import joblib

from OnlineRidgeRiver import *
from lean_adahedge import *
from bestLS_hindsight_together import *
from oridge_alwaysactive_implementable import *
import time

class All_linear_models: # can make it an abstract class that extends from all_models, but TODO for later
    '''
        TODO add class documentation
    '''
    def __init__(self, dir : str, filename: str, data_fil: pd.DataFrame, cat_cols_sig: list, groups : list):
        '''
            dir: name of head of directory, e.g. ./one_hotencoded
            filename: name of file
            data_fil: the dataframe with income <= 200k, no other processing done
            cat_cols_sig: list with names of all the categorical columns to be one-hot encoded
            groups: all the sensitive groups with underscore _ , e.g. ['SEX_1','SEX_2', 'RAC1P_1'....]
        '''
        self.timestamp = time.strftime("%Y%m%d-%H%M%S")
        self.dir = dir
        self.filename = filename + self.timestamp
        self.data_fil = data_fil
        self.cat_cols_sig = cat_cols_sig
        self.groups = groups
        
        
    def build_models(self, to_drop_groups = False, \
                    di_to_fill: dict = {'A_t': None, 'bls': None, 'Anh': None, 'oridge_implementable': None},\
                    to_shuffle = False, seed = 21) -> None:
        '''
            Goal:
                a) Saves numpy array (A_t) which is binary and has shape (T x len(sens_groups))
                b) Saves best squared loss (bls) in hindsight object
                c) Saves Ada normal hedge (Anh) with ridge meta experts
                d) Saved Online Ridge implementable, oridge_implementable, this is a single online ridge, regrets on subsequences computed by masking

            Input:

                di_to_fill : A_t, bls, Anh, oridge_implementable are added to dictionary
                to_drop_groups: Whether or not to drop sensitive columns
                to_shuffle: Whether or not to shuffle the dataframe

            Also Fills into di_to_fill dictioanry:
            A_t: numpy array
            bls: bestLS_hindsight.BestLS_Hindsight object
            Anh: Adanormal_sleepingexps.Adanormal_sleepingexps object
            oridge_implementable: oridge_alwaysactive_implementable.OnlineRidgeImplementable_alwaysactive object
        '''
        def build_bls(): # best square loss used to compute regret
            bls = BestLS_Hindsight_Together(self.N)
            for t in tqdm(range(self.T)):
                bls.update(A_t[t], X_dat.iloc[[t]], y_dat.iloc[t])
            bls.make_all_numpyarr() 
            bls.cumbestsqloss() # build cumulative loss of least squares on each group
            di_to_fill['bls'] = bls
            joblib.dump(bls, self.dir + 'models/bestsqloss/'+ self.filename +'.pkl')

        def build_Anh():
            experts = [River_OnlineRidge() for _ in range(self.N)] # Online ridge meta-experts
            Anh = Adanormal_sleepingexps(self.N, experts) #adanormal hedge
            for t in tqdm(range(self.T)):
                Anh.get_prob_over_experts(A_t[t]) #get probability over meta-experts
                Anh.update_metaexps_loss(A_t[t], X_dat.iloc[[t]], y_dat.iloc[t]) # update internal states of the meta-experts
            # fill in Anh cumulative regret curve before saving, to reduce disk space
            Anh.build_cumloss_curve(di_to_fill['bls'].best_sqloss, A_t)
            Anh.cleanup_for_saving() #compact size after cleanup, only essential external varaibles saved
            di_to_fill['Anh'] = Anh
            joblib.dump(Anh, self.dir + 'models/Anh/'+ self.filename +'.pkl')
        
        def build_oridge_implementable():
            oridge_implementable = OnlineRidgeImplementable_alwaysactive(X_dat, y_dat)
            oridge_implementable.fill_subsequence_regrets(A_t, di_to_fill['bls'].best_sqloss)
            di_to_fill['oridge_implementable'] = oridge_implementable
            joblib.dump(oridge_implementable, self.dir + 'models/oridge_implementable/'+ self.filename + '.pkl')

        # first one-hot encode self.data_fil using cat_cols_sig
        df_oh = one_hot(self.data_fil, self.cat_cols_sig)
        df_oh.drop(self.cat_cols_sig, axis=1, inplace = True) # drop OCCP, RACE, SEX, MAR..all categorical
        # shuffle if said to do so
        if to_shuffle:
            self.filename = self.filename + "_shuffled_"
            df_oh = df_oh.sample(frac = 1, random_state = seed)
        else:
            self.filename = self.filename + "_unshuffled_"
            
        # now collect build the A_t numpy array before dropping those columns (which can happen if dropped = True)
        A_tdf = df_oh[self.groups]
        A_tdf['alwayson'] = 1 # adds the always active / using all data "group"
        A_t = A_tdf.to_numpy()
        di_to_fill['A_t'] = A_t
        self.T  = A_t.shape[0] # shape of A_t is T x len(number of sens groups) + 1
        self.N  = A_t.shape[1]
        
        if to_drop_groups:
            self.filename = self.filename + "_dropped_"
            df_oh.drop(self.groups, axis = 1, inplace=True) # drop the onehot SEX_1, SEX_2, RAC1P_1,...
        else:
            self.filename = self.filename + "_undropped_"

        np.save(self.dir + 'nparrays/' + self.filename , A_t) # save the A_t array on disk

        # now min max scale all the features, all in [0, 1], and 
        df_oh = numeric_scaler(df_oh, df_oh.columns)
        X_dat = df_oh.drop('PINCP', axis=1) # dropping the income column
        y_dat = pd.DataFrame(df_oh['PINCP']) 
        build_bls()
        build_Anh()
        build_oridge_implementable()