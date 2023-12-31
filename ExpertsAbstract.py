import numpy as np
from abc import (
  ABC,
  abstractmethod,
)
#Abstract class for meta experts to be used by Adanormal hedge
class Expert(ABC):
    def __init__(self, name=None):
        self.name = name # can be OLS, Mult Weights etc
    
    @abstractmethod
    def get_ypred_t(self, x_t : np.ndarray) -> float:
        '''
            input:
                x_t : d element numpy array, context at time t
            returns:
                y_that: Experts predicted label in [0, 1], can be either regression [0, 1] or classification {0, 1}
        '''
        raise NotImplementedError
    
    @abstractmethod
    def update_t(self, y_t: float) -> None:
        '''
            Updates the internal state of the experts, this could be OLS \theta update, or MW update
            input: y_t the true label given by environment
            return:
                None
        '''
        raise NotImplementedError