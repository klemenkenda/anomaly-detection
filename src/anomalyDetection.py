from abc import abstractclassmethod, abstractmethod
from abc import ABC
from typing import Any, Dict, List, Union
import numpy as np
import sys
from statistics import mean
from datetime import datetime
import pickle
import sklearn.ensemble

sys.path.insert(0,'./src')
from output import OutputAbstract, TerminalOutput, FileOutput, KafkaOutput
from visualization import VisualizationAbstract, GraphVisualization,\
    HistogramVisualization



class AnomalyDetectionAbstract(ABC):
    memory_size: int
    memory: List[List[Any]]
    averages: List[List[int]]
    shifts: List[List[int]]
    time_features: List[str]

    input_vector_size: int
    outputs: List["OutputAbstract"]

    def __init__(self) -> None:
        self.memory = []

    @abstractmethod
    def message_insert(self, message_value: Dict[Any, Any]) -> None:
        assert len(message_value['test_value']) == self.input_vector_size, \
            "Given test value does not sattisfy input vector size"

    @abstractmethod
    def configure(self, conf: Dict[Any, Any]) -> None:
        self.input_vector_size = conf["input_vector_size"]
        
        if("averages" in conf):
            self.averages = conf["averages"]
        else:
            self.averages = []

        if("shifts" in conf):
            self.shifts = conf["shifts"]
        else:
            self.shifts = []

        if("time_features" in conf):
            self.time_features = conf["time_features"]
        else:
            self.time_features = []

        # Finds the largest element among averages and shifts
        self.memory_size = max(max(map(max, self.shifts))+1,
                               max(map(max, self.averages)))
    
    def feature_construction(self, value: List[Any], 
                             timestamp: str) -> Union[None, bool]:

        # Add new value to memory and slice it
        self.memory.append(value)
        self.memory = self.memory[-self.memory_size:]

        if(len(self.memory) < self.memory_size):
            # The memory does not contain enough records for all shifts and 
            # averages to be created
            return False

        # create new value to be returned
        new_value = value.copy()

        # Create average features
        new_value.extend(self.average_construction())

        # Create shifted features
        new_value.extend(self.shift_construction())

        # Create time features
        new_value.extend(self.time_features_construction(timestamp))

        return new_value

    def average_construction(self) -> None:
        averages = []
        np_memory = np.array(self.memory)

        # Loop through all features
        for feature_index in range(len(self.averages)):
            # Loop through all horizons we want the average of
            for interval in self.averages[feature_index]:
                values = np_memory[-interval:, feature_index]
                averages.append(mean(values))

        return averages

    def shift_construction(self) -> None:
        shifts = []

        # Loop through all features
        for feature_index in range(len(self.shifts)):
            # Loop through all shift values
            for look_back in self.shifts[feature_index]:
                shifts.append(self.memory[self.memory_size-(look_back+1)][feature_index])

        return shifts

    def time_features_construction(self, timestamp: str) -> None:
        time_features = []

        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f')

        # Requires datetime format
        # Check for keywords specified in time_features
        if("month" in self.time_features):
            time_features.append(int(dt.month))
        if ("day" in self.time_features):
            time_features.append(int(dt.day))
        if ("weekday" in self.time_features):
            time_features.append(int(dt.weekday()))
        if ("hour" in self.time_features):
            time_features.append(int(dt.hour))

        return time_features




class BorderCheck(AnomalyDetectionAbstract):
    """ works with 1D data and checks if the value is above, below or close
    to guven upper and lower limits 
    """
    UL: float
    LL: float
    warning_stages: List[float]
    outputs: List["OutputAbstract"]
    visualization: List["VisualizationAbstract"]

    def __init__(self, conf: Dict[Any, Any] = None) -> None:
        super().__init__()
        if(conf is not None):
            self.configure(conf)


    def configure(self, conf: Dict[Any, Any] = None) -> None:
        super().configure(conf)
        self.LL = conf["LL"]
        self.UL = conf["UL"]

        self.warning_stages = conf["warning_stages"]
        self.warning_stages.sort()

        # initialize all outputs
        self.outputs = [eval(o) for o in conf["output"]]

        # configure all outputs
        output_configurations = conf["output_conf"]
        for o in range(len(self.outputs)):
            self.outputs[o].configure(output_configurations[o])

        # If configuration is specified configure it
        if ("visualization" in conf):
            print(conf["visualization"])
            self.visualization = eval(conf["visualization"])
            visualization_configurations = conf["visualization_conf"]
            self.visualization.configure(visualization_configurations)
        else:
            self.visualization = None

    def message_insert(self, message_value: Dict[Any, Any]) -> None:
        super().message_insert(message_value)
        value = message_value["test_value"]
        value = value[0]
        timestamp = message_value["timestamp"]

        value_normalized = 2*(value - (self.UL + self.LL)/2) / \
            (self.UL - self.LL)
        status = "OK"
        status_code = 1

        if(value_normalized > 1):
            status = "Error: measurement above upper limit"
            status_code = -1
        elif(value_normalized < -1):
            status = "Error: measurement below lower limit"
            status_code = -1
        else:
            for stage in range(len(self.warning_stages)):
                if(value_normalized > self.warning_stages[stage]):
                    status = "Warning" + str(stage) + \
                        ": measurement close to upper limit."
                    status_code = 0
                elif(value_normalized < -self.warning_stages[stage]):
                    status = "Warning" + str(stage) + \
                        ": measurement close to lower limit."
                    status_code = 0
                else:
                    break

        for output in self.outputs:
            output.send_out(status=status, value=value)

        if(self.visualization is not None):
            lines = [value]
            self.visualization.update(value=lines, timestamp=timestamp,
                                      status_code=status_code)


class EMA(AnomalyDetectionAbstract):
    UL: float
    LL: float
    N: int
    smoothing: float
    EMA: List[float]
    sigma: List[float]
    numbers: List[float]
    timestamp: List[Any]
    visualization: List["VisualizationAbstract"]
    outputs: List["OutputAbstract"]

    def __init__(self, conf: Dict[Any, Any] = None) -> None:
        super().__init__()
        if(conf is not None):
            self.configure(conf)

    def configure(self, conf: Dict[Any, Any] = None) -> None:
        super().configure(conf)
        self.LL = conf["LL"]
        self.UL = conf["UL"]
        self.warning_stages = conf["warning_stages"]
        self.warning_stages.sort()
        self.N = conf['N']
        self.smoothing = 2/(self.N+1)
        self.EMA = []
        self.sigma = []
        self.numbers = []
        self.timestamps = []

        self.outputs = [eval(o) for o in conf["output"]]
        # configure all outputs
        output_configurations = conf["output_conf"]
        for o in range(len(self.outputs)):
            self.outputs[o].configure(output_configurations[o])

        if ("visualization" in conf):
            self.visualization = eval(conf["visualization"])
            visualization_configurations = conf["visualization_conf"]
            self.visualization.configure(visualization_configurations)
        else:
            self.visualization = None

    def message_insert(self, message_value: Dict[Any, Any]):
        super().message_insert(message_value)
        self.numbers.append(message_value['test_value'][0])
        self.timestamps.append(message_value['timestamp'])
        if(len(self.EMA) == 0):
            self.EMA.append(self.numbers[-1])
        else:
            new = self.numbers[-1] * self.smoothing + self.EMA[-1] *\
                (1-self.smoothing)
            self.EMA.append(new)

        if(len(self.numbers) == 1):
            self.sigma.append(0)
        elif(len(self.numbers) < self.N):
            self.sigma.append(np.std(self.numbers))
        else:
            self.sigma.append(np.std(self.numbers[-self.N:]))


        
        value_normalized = 2*(self.EMA[-1] - (self.UL + self.LL)/2) / \
            (self.UL - self.LL)
        status = "OK"
        status_code = 1

        if(value_normalized > 1):
            status = "Error: EMA above upper limit"
            status_code = -1
        elif(value_normalized < -1):
            status = "Error: EMA below lower limit"
            status_code = -1
        else:
            for stage in range(len(self.warning_stages)):
                if(value_normalized > self.warning_stages[stage]):
                    status = "Warning" + str(stage) + \
                        ": EMA close to upper limit."
                    status_code = 0
                elif(value_normalized < -self.warning_stages[stage]):
                    status = "Warning" + str(stage) + \
                        ": EMA close to lower limit."
                    status_code = 0
                else:
                    break





        for output in self.outputs:
            output.send_out(timestamp=message_value["timestamp"],
                            value=message_value["test_value"])
            output.send_out(status=status, value=value)

        mean = self.EMA[-1]
        sigma = self.sigma[-1]
        lines = [self.numbers[-1], mean, mean+sigma, mean-sigma]
        timestamp = self.timestamps[-1]
        if(self.visualization is not None):
            self.visualization.update(value=lines, timestamp=message_value["timestamp"],
            status_code = 0)


class IsolationForest(AnomalyDetectionAbstract):
    def configure(self, conf: Dict[Any, Any] = None) -> None:
        super().configure(conf)

        # Outputs and visualization initialization and configuration
        self.outputs = [eval(o) for o in conf["output"]]
        output_configurations = conf["output_conf"]
        for o in range(len(self.outputs)):
            self.outputs[o].configure(output_configurations[o])
        if ("visualization" in conf):
            self.visualization = eval(conf["visualization"])
            visualization_configurations = conf["visualization_conf"]
            self.visualization.configure(visualization_configurations)
        else:
            self.visualization = None


        if("load_model_from" in conf):
            self.model = self.load_model(conf["load_model_from"])
        elif("train_data" in conf):
            self.train_model(conf)

    def message_insert(self, message_value: Dict[Any, Any]) -> None:
        super().message_insert(message_value)

        value = message_value["test_value"]
        timestamp = message_value["timestamp"]

        feature_vector = super().feature_construction(value=value,
                                                      timestamp=timestamp)

    

        if (feature_vector == False):
            # If this happens the memory does not contain enough samples to
            # create all additional features.

            # Send undefined message to output
            for output in self.outputs:
                output.send_out(timestamp=message_value['timestamp'],
                                value=None)
            
            # And to visualization
            if(self.visualization is not None):
                lines = [value[0]]
                #self.visualization.update(value=[None], timestamp=timestamp,
                #                          status_code=2)
            return
        else:
            feature_vector = np.array(self.shift_construction())

            isolation_score = self.model.decision_function(feature_vector.T.reshape(1, -1))
            for output in self.outputs:
                output.send_out(timestamp=message_value['timestamp'],
                                value=isolation_score)
            

            if(self.visualization is not None):
                lines = [value[0]]
                self.visualization.update(value=isolation_score, timestamp=timestamp,
                                          status_code=1)
            return

    def save_model(self, filename):
        with open("models/" + filename, 'wb') as f:
            pickle.dump(self.model, f)

    def load_model(self, filename):
        with open(filename, 'rb') as f:
            clf = pickle.load(f)
        return(clf)

    def train_model(self, conf):
     #load data from location stored in "filename"
        data = np.loadtxt(conf["train_data"], skiprows=1, delimiter = ",", usecols=(1,))

        features = []
        N = conf["train_conf"]["max_features"]
        for i in range(N, len(data)):
            features.append(np.array(data[i-N:i]))

        #fit IsolationForest model to data
        self.model = sklearn.ensemble.IsolationForest(
            max_samples = conf["train_conf"]["max_samples"],
            max_features = N
            ).fit(features)

        self.save_model(conf["train_conf"]["model_name"])


class PCA(AnomalyDetectionAbstract):
    def configure(self, conf: Dict[Any, Any] = None) -> None:
        super().configure(conf)

        # Outputs and visualization initialization and configuration
        self.outputs = [eval(o) for o in conf["output"]]
        output_configurations = conf["output_conf"]
        for o in range(len(self.outputs)):
            self.outputs[o].configure(output_configurations[o])
        if ("visualization" in conf):
            self.visualization = eval(conf["visualization"])
            visualization_configurations = conf["visualization_conf"]
            self.visualization.configure(visualization_configurations)
        else:
            self.visualization = None

        if("load_model_from" in conf):
            self.model = self.load_model(conf["load_model_from"])
        elif("train_data" in conf):
            self.train_model(conf)

    def message_insert(self, message_value: Dict[Any, Any]) -> None:
        super().message_insert(message_value)

        value = message_value["test_value"]
        timestamp = message_value["timestamp"]

        feature_vector = super().feature_construction(value=value,
                                                      timestamp=timestamp)

    

        if (feature_vector == False):
            # If this happens the memory does not contain enough samples to
            # create all additional features.

            # Send undefined message to output
            for output in self.outputs:
                output.send_out(timestamp=message_value['timestamp'],
                                value=None)
            
            # And to visualization
            if(self.visualization is not None):
                lines = [value[0]]
                #self.visualization.update(value=[None], timestamp=timestamp,
                #                          status_code=2)
            return
        else:
            feature_vector = np.array(self.shift_construction())

            PCA_transformed = self.model.transform(feature_vector.reshape(1, -1))
            for output in self.outputs:
                output.send_out(timestamp=message_value['timestamp'],
                                value=PCA_transformed)
            

            if(self.visualization is not None):
                lines = PCA_transformed[0]
                self.visualization.update(value=lines, timestamp=timestamp,
                                          status_code=1)
            return

    def save_model(self, filename):
        with open("models/" + filename, 'wb') as f:
            pickle.dump(self.model, f)

    def load_model(self, filename):
        with open(filename, 'rb') as f:
            clf = pickle.load(f)
        return(clf)

    def train_model(self, conf):
     #load data from location stored in "train_data"
        data = np.loadtxt(conf["train_data"], skiprows=1, delimiter = ",", usecols=(1,))

        features = []
        N_components = conf["train_conf"]["N_components"]
        N_past_data = conf["train_conf"]["N_past_data"]
        for i in range(N_past_data, len(data)):
            features.append(np.array(data[i-N_past_data:i]))

        #fit IsolationForest model to data
        self.model = sklearn.decomposition.PCA(n_components = N_components)
        self.model.fit(features)
        self.save_model(conf["train_conf"]["model_name"])
 

    