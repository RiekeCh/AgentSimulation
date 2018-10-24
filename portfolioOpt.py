#-----------------------------------------------------------------------------
#
# Autor: Christian Rieke
# Datum: 21.10.2018
#
# Beschreibung: Optimierung Portfolio
#
# Letzte Änderung:
#
#           21.10.2018  Aufbau der Klasse --> Ziel: einfache Optimierung
# 
#-----------------------------------------------------------------------------

# Laden der Abhängigkeiten
import numpy as np
from gurobipy import *
import matplotlib.pyplot as plt
import pandas as pd

class powerPlantPortfolio:
    
        def __init__(self,dt=0.25):

            self.m = Model('portfolio')                 # Anlegen eines Models ins Gurobi    
#            self.m.Params.OutputFlag=0                  # keine Ausgabe der Optimierungsergebnisse
            self.dt = dt                                # Zeitschrittweite/ Auflösung
            self.powerPlants = []                       # Anlegen einer Liste mit allen Kraftwerken im Portfolio
            
            self.powerPrice = []                        # Preiszeitreihe Strom
            self.coPrice = []                           # Preiszeitreihe Co2
            self.gasPrice = []                          # Preiszeitreihe Gas
            self.lignitePrice = 0                       # Preis Braunkohle
            self.coalPrice = 0                          # Preis Steinkohle
            self.nucPrice = 0                           # Preis Uranbrennstäbe
            
            self.T = 0                                  # zu berechnennde Zeitschritte
            self.t = np.arange(self.T)                  # Zeitschritte [0,1,2,3,...]
            
            self.results = {}                           # Ergebnisse der Optimierung

            print('Portfolio initialisiert')
            
            pass
        
        def setPrices(self, power,co,gas,lignite,coal,nuc): # Setzen der Preise und Länge der Optimierung
            
            # --> Preise
            self.powerPrice = power
            self.coPrice = co
            self.gasPrice = gas
            self.lignitePrice = lignite
            self.coalPrice = coal
            self.nucPrice = nuc
            # --> Länge (Zeitschritte)
            self.T = len(power)
            self.t = np.arange(self.T)
            
            print('Preise und Zeitschritte gesetzt')
            
            pass
        
        def addPowerPlant(self,powerPlant): # Fügt ein Kraftwerk zum Portfolio hinzu
            
            # Eintrag zur Kraftwerksliste hinzufügen
            self.powerPlants.append(powerPlant)
            
            if powerPlant['typ'] == 'konv':
                # Initiales Ergebnis für konvetionelle Kraftwerke anlegen
                result = {'PTs'      : [],
                          'P0'       : powerPlant['P0'],
                          'on'       : powerPlant['on'],
                          'FTs'      : [],
                          'ETs'      : [],
                          'profit'   : 0,
                          'profitTs' : []}
            if powerPlant['typ'] == 'storage':
                # Initiales Ergebnis für Speicher anlegen
                result = {'PTs'      : [],
                          'VTs'      : [],
                          'P+0'      : powerPlant['P+0'],
                          'P-0'      : powerPlant['P-0'],
                          'V0'       : powerPlant['V0'],
                          'profit'   : 0,
                          'profitTs' : []}
                
            self.results.update({powerPlant['name'] : result})
            
            print('Kraftwerk ' + powerPlant['name'] + ' hinzugefügt')
            
            pass
        
        def __addconvPlant(self,powerPlant): # Fügt die Nebenbedingungen konv. Kraftwerk hinzu
            
            name = powerPlant['name']   # --> Name des Kraftwerks
            
            # Leistung zu jedem Zeitschritt (Grenzen: 0,inf)
            power = self.m.addVars(self.t, vtype=GRB.CONTINUOUS, name='P_' + name,
                                   lb=0,ub=GRB.INFINITY)
            # Brennstoffkosten zu jedem Zeitschritt (Grenzen: -inf,inf)
            fuel = self.m.addVars(self.t, vtype=GRB.CONTINUOUS, name='F_' + name,
                                  lb=-GRB.INFINITY,ub=GRB.INFINITY)
            # Kosten der Emissionen zu jedem Zeitschritt (Grenzen: 0,inf)        
            emission = self.m.addVars(self.t, vtype=GRB.CONTINUOUS, name='E_' + name,
                                  lb=0,ub=GRB.INFINITY)
            # Gewinn zu jedem Zeitschritt (Grenzen: -inf,inf)
            profit = self.m.addVars(self.t, vtype=GRB.CONTINUOUS, name='Profit_' + name,
                                    lb=-GRB.INFINITY,ub=GRB.INFINITY)
            # Binäre Variable für an oder aus zu jedem Schritt {0,1}
            on = self.m.addVars(self.t, vtype=GRB.BINARY, name='On_' + name)
            # Gewinnzeitreihe
            self.m.addConstrs(profit[i] == power[i] * self.powerPrice[i] for i in self.t)
            # Brennstoffkosten je Kraftwerkstyp
            if powerPlant['fuel'] == 'lignite':
                self.m.addConstrs(fuel[i] == power[i]/powerPlant['eta'] * self.lignitePrice for i in self.t)
            if powerPlant['fuel'] == 'coal':
                self.m.addConstrs(fuel[i] == power[i]/powerPlant['eta'] * self.coalPrice for i in self.t)
            if powerPlant['fuel'] == 'gas':
                self.m.addConstrs(fuel[i] == power[i]/powerPlant['eta'] * self.gasPrice[i] for i in self.t)
            if powerPlant['fuel'] == 'nuc':
                self.m.addConstrs(fuel[i] == power[i]/powerPlant['eta'] * self.nucPrice for i in self.t)
            # Emissionkosten
            self.m.addConstrs(emission[i] == power[i]*powerPlant['chi'] * self.coPrice[i] for i in self.t)
            # Berücksichtigung der Startbedingungen (Wie ist der Zustand meines KW nach der letzten Optimierung)
            self.m.addConstr(power[0] <= self.results[name]['P0'] + powerPlant['grad+'])
            self.m.addConstr(power[0] >= self.results[name]['P0'] - powerPlant['grad-'])
            # Berücksichtigung der Gradienten
            self.m.addConstrs(power[i] <= power[i-1]+powerPlant['grad+'] for i in self.t[1:])
            self.m.addConstrs(power[i] >= power[i-1]-powerPlant['grad-'] for i in self.t[1:])
            # Wenn das Kraftwerk läuft --> [Pmin,Pmax]
            self.m.addConstrs(power[i] >= on[i] * powerPlant['powerMin'] for i in self.t)
            self.m.addConstrs(power[i] <= on[i] * powerPlant['powerMax'] for i in self.t)
            # Berücksichtigung von Stillstandszeit
            if self.results[name]['on'] < 0:
                self.m.addConstrs(on[i]== 0 for i in np.arange(powerPlant['stopTime']+self.results[name]['on']))
            for i in self.t[1:]:
                start = i+1
                end = np.min([i+powerPlant['stopTime']-1,self.T])
                tau = np.arange(start,end)
                self.m.addConstrs(on[i-1]-on[i] <= 1-on[k] for k in tau)
            # Berücksichtigung von Laufzeit
            if self.results[name]['on'] > 0:
                self.m.addConstrs(on[i]== 1 for i in np.arange(powerPlant['runTime']-self.results[name]['on']))
            for i in self.t[1:]:
                start = i+1
                end = np.min([i+powerPlant['runTime']-1,self.T])
                tau = np.arange(start,end)
                self.m.addConstrs(on[i]-on[i-1] <= on[k] for k in tau)
            # Einbinden der NB in das Model
            self.m.update()
            
            print('Nebenbedingungen für ' + name + ' hinzugefügt')
            
            pass
        
        def __addStorage(self,powerPlant):
            
            name = powerPlant['name']   # --> Name des Kraftwerks
            
            # Leistung zu jedem Zeitschritt (Grenzen: 0,inf)
            power = self.m.addVars(self.t, vtype=GRB.CONTINUOUS, name='P_' + name,
                                   lb=-GRB.INFINITY,ub=GRB.INFINITY)
            # Speicherfüllstand zu jedem Zeitschritt (Grenzen: Vmin, Vmax)
            volume = self.m.addVars(self.t, vtype=GRB.CONTINUOUS, name='V_' + name,
                                   lb=powerPlant['VMin'],ub=powerPlant['VMax'])
            # Ladeleistung zu jedem Zeitschritt (Grenzen: 0, Pmax)
            pP = self.m.addVars(self.t, vtype=GRB.CONTINUOUS, name='P+_' + name,
                                   lb=0,ub=powerPlant['P+_Max'])
            # Entladeleistung zu jedem Zeitschritt (Grenzen: 0. Pmax)
            pM = self.m.addVars(self.t, vtype=GRB.CONTINUOUS, name='P-_' + name,
                                   lb=0,ub=powerPlant['P-_Max'])
            # Binäre Variable für den Betriebszustand zu jedem Schritt {0,1}
            on = self.m.addVars(self.t, vtype=GRB.BINARY, name='On_' + name)
            # Gewinn zu jedem Zeitschritt (Grenzen: -inf,inf)
            profit = self.m.addVars(self.t, vtype=GRB.CONTINUOUS, name='Profit_' + name,
                                    lb=-GRB.INFINITY,ub=GRB.INFINITY)
            # Leistung, die dem Portflio hinzugefügrt wird
            self.m.addConstrs(power[i] == -pP[i] + pM[i] for i in self.t)
            # maximale Ladeleistung
            self.m.addConstrs(pP[i] <= on[i] * powerPlant['P+_Max'] for i in self.t)
            # minimale Ladeleistung
            self.m.addConstrs(pP[i] >= on[i] * powerPlant['P+_Min'] for i in self.t)
            # maximale Entladeleistung
            self.m.addConstrs(pM[i] <= (1-on[i]) * powerPlant['P-_Max'] for i in self.t)
            # minimale Entlladeleistung
            self.m.addConstrs(pM[i] >= (1-on[i]) * powerPlant['P-_Min'] for i in self.t)
            # Speicherfüllstand zu Beginn
            self.m.addConstr(volume[0] == powerPlant['V0'] + self.dt* (powerPlant['eta+'] * pP[0] - pM[0]/powerPlant['eta-']))
            # weitere Speicherfüllstände
            self.m.addConstrs(volume[i] == volume[i-1] + self.dt* (powerPlant['eta+'] * pP[i] - pM[i]/powerPlant['eta-']) for i in self.t[1:])
            # Gewinnzeitriehe
            self.m.addConstrs(profit[i] == power[i] * self.powerPrice[i] for i in self.t)
            # Gradienten Laden
            self.m.addConstr(pP[0] <= self.results[name]['P+0'] + powerPlant['grad++'])
            self.m.addConstr(pP[0] >= self.results[name]['P+0'] - powerPlant['grad+-'])
            self.m.addConstrs(pP[i] <= pP[i-1]+powerPlant['grad++'] for i in self.t[1:])
            self.m.addConstrs(pP[i] >= pP[i-1]-powerPlant['grad+-'] for i in self.t[1:])
            # Gradienten Entladen
            self.m.addConstr(pM[0] <= self.results[name]['P-0'] + powerPlant['grad-+'])
            self.m.addConstr(pM[0] >= self.results[name]['P-0'] - powerPlant['grad--'])
            self.m.addConstrs(pM[i] <= pM[i-1]+powerPlant['grad-+'] for i in self.t[1:])
            self.m.addConstrs(pM[i] >= pM[i-1]-powerPlant['grad--'] for i in self.t[1:])
            # Einbinden der NB in das Model
            self.m.update()
            
            print('Nebenbedingungen für ' + name + ' hinzugefügt')
            
            pass

        def buildModel(self): # Aufbau des Optimierungsmodells
            # Füge für jedes Kraftwerk im Portfolio die Nebenbedingungen hinzu
            for powerPlant in self.powerPlants:
                if powerPlant['typ'] == 'konv':
                    self.__addconvPlant(powerPlant)
                if powerPlant['typ'] == 'storage':
                    self.__addStorage(powerPlant)

            # Gesamtleistung im Portfolio
            power = self.m.addVars(self.t,vtype=GRB.CONTINUOUS, name='P', lb=-GRB.INFINITY,ub=GRB.INFINITY)
            pPower = [x for x in self.m.getVars() if 'P_' in x.VarName]
            self.m.addConstrs(power[i] == quicksum(p for p in pPower if '[%i]' %i in p.VarName) for i in self.t) 
            # Brennstoffkosten im Portfolio
            fuel = self.m.addVars(self.t,vtype=GRB.CONTINUOUS, name='F',  lb=-GRB.INFINITY,ub=GRB.INFINITY)
            pFuel = [x for x in self.m.getVars() if 'F_' in x.VarName]
            self.m.addConstrs(fuel[i] == quicksum(f for f in pFuel if '[%i]' %i in f.VarName) for i in self.t)
            # Emissionskosten im Portfolio
            emission = self.m.addVars(self.t,vtype=GRB.CONTINUOUS, name='E', lb=-GRB.INFINITY,ub=GRB.INFINITY)
            pEmssion = [x for x in self.m.getVars() if 'E_' in x.VarName]
            self.m.addConstrs(emission[i] == quicksum(e for e in pEmssion if '[%i]' %i in e.VarName) for i in self.t)
            # Gewinn des Portfolios
            profit = self.m.addVar(vtype=GRB.CONTINUOUS, name='Profit', lb=-GRB.INFINITY,ub=GRB.INFINITY)
            self.m.addConstr(profit == quicksum(power[i] * self.powerPrice[i] for i in self.t))
            # Setzen der Zielfunktion --> Maximiere Gewinn
            self.m.setObjective(profit - quicksum(fuel[i] - emission[i] for i in self.t) ,GRB.MAXIMIZE)
            # Einbinden der NB in das Model
            self.m.update()

            pass
        
        def __getResults(self):
            
            for powerPlant in self.powerPlants:
                name = powerPlant['name']                   # Names des KW
                typ = powerPlant['typ']                     # Typ des KW
                # Ergebnisse für konv. Kraftwerke
                if typ == 'konv':
                    powerTs = []                            # Fahrplan Kraftwerk
                    fuelTs = []                             # Brennstoffkosten
                    EmissionTs = []                         # Emissionen
                    profitTs = []                           # Gewinn/Kosten
                    onTs = []                               # in Betrieb
                    # Abfrage der Optimierungsergbenisse
                    for i in self.t:
                        powerTs.append(self.m.getVarByName('P_%s[%i]' %(name,i)).x)
                        fuelTs.append(self.m.getVarByName('F_%s[%i]' %(name,i)).x)
                        EmissionTs.append(self.m.getVarByName('E_%s[%i]' %(name,i)).x)
                        profitTs.append(self.m.getVarByName('Profit_%s[%i]' %(name,i)).x)
                        onTs.append(self.m.getVarByName('On_%s[%i]' %(name,i)).x)
                    # Speichern der Ergebnisse
                    self.results[name]['PTs'] = powerTs
                    self.results[name]['FTs'] = fuelTs
                    self.results[name]['ETs'] = EmissionTs
                    self.results[name]['profitTs'] = profitTs
                    self.results[name]['profit'] = np.sum(profitTs)
                    self.results[name]['P0'] = powerTs[i]
                    # Bestimmen der Betriebszeiten (in Betrieb oder Stillstand)
                    onTs = np.diff(onTs)
                    lastSwitch = 0; counter = 0
                    for ts in onTs:
                        if ts != 0:
                            lastSwitch = counter
                        counter += 1
                    if onTs[lastSwitch] == 1:   # Anfahrt
                        on = self.T-lastSwitch-1
                    else:                       # Abfahrt
                        on = -1*(self.T-lastSwitch+1) 
                    self.results[name]['on'] = on
                # Ergebnisse für Speicher    
                if typ == 'storage':
                    powerTs = []                            # Fahrplan Kraftwerk
                    volumeTs = []                           # Füllstände
                    profitTs = []                           # Gewinn/Kosten
                    plusTs = []                             # Ladeleistung
                    minusTs = []                            # Entladeleistung
                    for i in self.t:
                        powerTs.append(self.m.getVarByName('P_%s[%i]' %(name,i)).x)
                        volumeTs.append(self.m.getVarByName('V_%s[%i]' %(name,i)).x)
                        profitTs.append(self.m.getVarByName('Profit_%s[%i]' %(name,i)).x)
                        plusTs.append(self.m.getVarByName('P+_%s[%i]' %(name,i)).x)
                        minusTs.append(self.m.getVarByName('P-_%s[%i]' %(name,i)).x)
                    # Speichern der Ergebnisse
                    self.results[name]['PTs'] = powerTs
                    self.results[name]['VTs'] = volumeTs
                    self.results[name]['P+0'] = plusTs[i]
                    self.results[name]['P-0'] = minusTs[i]
                    self.results[name]['profit'] = np.sum(profitTs)
                    self.results[name]['profitTs'] = profitTs
                    
                pass                    
        
        def runOpt(self,plot = True):

            try: 
                self.m.optimize()
                self.__getResults()
                
                if plot:
                    self.__plotResults()

            except:
                print('Fehler während der Optimierung')
            
            pass
        
        def __plotResults(self):

            power = np.vstack([self.results[key]['PTs'] for key in self.results.keys()])
#            fuel = np.vstack([self.results[name]['FTs'] for name in names])
#            emission = np.vstack([self.results[name]['ETs'] for name in names])
            
            labels = self.results.keys()
            
            fig, ax = plt.subplots(1,1)
            # --> Power Plot
            ax.stackplot(self.t, power, labels=labels)
            ax.legend(loc='upper left')
            ax.set_title('Power')
            ax.set_xlabel('time [h]')
            ax.set_ylabel('Power [MW]')
            
            # --> Fuel Plot
#            ax[1].stackplot(self.t, fuel, labels=labels)
#            ax[1].legend(loc='upper left')
#            ax[1].set_title('Fuel')
#            ax[1].set_xlabel('time [h]')
#            ax[1].set_ylabel('Costs [€]')
#            # --> Emission Plot
#            ax[2].stackplot(self.t, emission, labels=labels)
#            ax[2].legend(loc='upper left')
#            ax[2].set_title('Emissions')
#            ax[2].set_xlabel('time [h]')
#            ax[2].set_ylabel('Costs [€]')
            
            pass
            
                    
if __name__ == "__main__":
    
    power = np.random.permutation(24)+10
    gas = np.random.permutation(24)
    co = np.random.permutation(24)
    lignite = 2
    coal = 4
    nuc = 1
    
    myPortfolio = powerPlantPortfolio()
    myPortfolio.setPrices(power,co,gas,lignite,coal,nuc)    
    
    myPlan1 = {'typ'        :   'konv',
               'name'       :   'WW',
               'fuel'       :   'gas',
               'powerMax'   :   750,
               'powerMin'   :   100,
               'eta'        :   0.35,
               'chi'        :   0.21,
               'grad+'      :   100,
               'grad-'      :   100,
               'stopTime'   :   8,
               'runTime'    :   7,
               'P0'         :   0,
               'on'         :   -2}
    
    myPlan2 = {'typ'        :   'konv',
               'name'       :   'NR',
               'fuel'       :   'gas',
               'powerMax'   :   1000,
               'powerMin'   :   350,
               'eta'        :   0.45,
               'chi'        :   0.15,
               'grad+'      :   150,
               'grad-'      :   150,
               'stopTime'   :   3,
               'runTime'    :   2,
               'P0'         :   400,
               'on'         :   1}
    
    myPlan3 = {'typ'        :   'storage',
               'name'       :   'VI',
               'VMax'       :   1230,
               'VMin'       :   100,
               'P+_Max'     :   500,
               'P+_Min'     :   100,
               'P-_Max'     :   450,
               'P-_Min'     :   50,
               'eta+'       :   0.85,
               'eta-'       :   0.85,
               'grad++'     :   75,
               'grad+-'     :   68,
               'grad-+'     :   50,
               'grad--'     :   45,
               'P+0'        :   0,
               'P-0'        :   70,
               'V0'         :   500}
    
    
    myPortfolio.addPowerPlant(myPlan1)
    myPortfolio.addPowerPlant(myPlan2)
    myPortfolio.addPowerPlant(myPlan3)          
    myPortfolio.buildModel()
    myPortfolio.runOpt()
#    myPortfolio.buildModel()
#    myPortfolio.runOpt()            