#-----------------------------------------------------------------------------
#
# Tutorial Mesa Agentbased Simulation
#
# 11.10.2018
#
# Christian Rieke
#
#-----------------------------------------------------------------------------


# model.py
from mesa import Agent, Model
from mesa.time import RandomActivation
import random
import matplotlib.pyplot as plt
from mesa.space import MultiGrid
import numpy as np
from mesa.datacollection import DataCollector
import pandas as pd


class MoneyAgent(Agent):
    """An agent with fixed initial wealth."""
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.wealth = 1
        
    def step(self):
        # The agent's step will go here.
        # print('My Name is: %.1f' %self.unique_id)
        # print('I have : %.2f Unit(s) \n' %self.wealth)
        self.move()
        if self.wealth > 0:
            self.give_money()
    
    def move(self):
        possible_steps = self.model.grid.get_neighborhood(
            self.pos,
            moore=True,
            include_center=False)
        new_position = random.choice(possible_steps)
        self.model.grid.move_agent(self, new_position)
        
    def give_money(self):
        cellmates = self.model.grid.get_cell_list_contents([self.pos])
        if len(cellmates) > 1:
            other = random.choice(cellmates)
            other.wealth += 1
            self.wealth -= 1

def compute_gini(model):
    agent_wealths = [agent.wealth for agent in model.schedule.agents]
    x = sorted(agent_wealths)
    N = model.num_agents
    B = sum( xi * (N-i) for i,xi in enumerate(x) ) / (N*sum(x))
    return (1 + (1/N) - 2*B)
                

class MoneyModel(Model):
    """A model with some number of agents."""
    def __init__(self, N, width, height):
        self.num_agents = N
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(width, height, True)
        # self.num = 1
        # Create agents
        for i in range(self.num_agents):
            a = MoneyAgent(i, self)
            self.schedule.add(a)
            x = random.randrange(self.grid.width)
            y = random.randrange(self.grid.height)
            self.grid.place_agent(a, (x, y))
        
        self.datacollector = DataCollector(
                model_reporters={"Gini": compute_gini},  # A function to call
                agent_reporters={"Wealth": "wealth"})  # An agent attribute
            
    def step(self):
        '''Advance the model by one step.'''
        # print('run %.0f' %self.num)
        self.datacollector.collect(self)
        self.schedule.step()
        # self.num += 1
        

        

if __name__ == '__main__':
    
    model = MoneyModel(75, 10, 10)
    for i in range(100):
        model.step()
     
    gini = model.datacollector.get_model_vars_dataframe()   
    gini.plot()  
    agent_wealth = model.datacollector.get_agent_vars_dataframe()
#    agent_counts = np.zeros((model.grid.width, model.grid.height))
#    
#    for cell in model.grid.coord_iter():
#        cell_content, x, y = cell
#        agent_count = len(cell_content)
#        agent_counts[x][y] = agent_count
#    plt.imshow(agent_counts, interpolation='nearest')
#    plt.colorbar()