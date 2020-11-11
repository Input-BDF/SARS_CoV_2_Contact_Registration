'''
Created on 11.11.2020

@author: Input
'''

import threading

__all__ = ['CoolDown']

#TODO: implement as fulltime running queue thread. maybee use also queue module
class CoolDown(set):
    '''
    cooldown queue set
    '''
    def add(self, item, ttl):
        '''
        item: item so queue
        ttl: time to live in seconds. item will be removed after ttl is reached 
        '''
        if item not in self:
            set.add(self, item)
            t = threading.Timer(ttl, self.check_remove, args=[item,])
            t.start()

    def check_remove(self, item):
        '''
        test if item is still in set and remove it
        '''
        if item in self:
            self.remove(item)

if __name__ == '__main__':
    pass