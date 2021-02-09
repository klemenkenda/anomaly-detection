# Anomaly detection for streaming data

## Usage
`python main.py [-h] [-c CONFIG] [--f]`

| Short   |      Long     |  Description |
|----------|-------------|------|
| `-h` | `--help` | show help |
| `-c CONFIG` | `--config CONFIG` | name of the config file located in configuration folder (example: `config.json`) |
| `-f` | `--file` | If this flag is used the program will read data from file specified in config file instead of kafka stream|
| `-fk` | `--filekafka` | If this flag is used the program will read data from file specified in config file and then from kafka stream|

## Architecture
The anomaly detection program consists of three main types of components:
1. Consumer component
2. Anomaly detection component
3. Output component
Each component has many implementations that are interchangeable. Which ones are used depends on the task the program is solving.
There is also an optional Visualization component which doesn't effect the general workflow and is used for streaming data visualization.

### Configuration file
The program is configured through configuration file specified with -c flag (located in configuration folder). It is a JSON file with the following structure:
```
{
    ...
    consumer configuration
    ...
    "anomaly_detection_alg": "anomaly detection algorithm",
    "anomaly_detection_conf": {
        ...
        anomaly detection configuration
        ...
        "output": ["list of output components"],
        "output_conf": ["list of output components configurations"],
        "visualization": "visualization component", # optional
        "visualization_conf": "visualization component configuration" # optional
    }
}
```
The specific configurations for components will be presented in following chapters
For more details see example configuration files in configuration folder.

### Consumer
Consumer components differ in where the data is read from.
1. **Kafka consumer:** Data is read from kafka stream from a specified topic. The conciguration file must specify following parameters:
   * bootstrap_servers: Kafka server. (example: ["localhost:9092"])
   * auto_offset_reset: Where the consumer starts to read messages. If "latest", when comsumer is started, it will continue reading from the message where it last left off. If "earliest" it will read from the oldest available message onwards. (example: "latest")
   * enable_auto_commit": If True , the consumer’s offset (the point in the topic where messages are read) will be periodically committed in the background. Otherwise offsets can be commited manually. (example: "True")
   * group_id: The name of the consumer group. (example "my-group")
   * value_deserializer":  Any callable that takes a raw message value and returns a deserialized value. (example "lambda x: loads(x.decode('utf-8'))")
   * topics: A list of topics streaming the data. (example ["anomaly_detection"])

   A message in kafka topic must contain two fields:
   * timestamp: Contains a timestamp of the data in datastream in datetime format.
   * test_value: Contains an array (a feature vector) of values.

2. **File consumer:** Data is read from a csv or JSON file. The csv can have a "timestamp" column. All other columns are considered values for detecting anomalies. The JSON file must be of shape `{"data": [{"timestamp": ..., test_value": [value1, value2, ...]}, ...]}`. All timestamp values must be strings in datetime format. The configuration file must specify the following parameters:
   * file_name: The name of the file with the data, located in data/consumer/ directory. (example: "sin.csv")

3. **File kafka consumer:** Used when first part of the datastream is written in a file and then continues as kafka stream. Also it can be used for model-less aproaches as a way of "learnig" from train data, so that the anomaly detection would work better on the actual kafka input stream. <br> 
The csv input file can have a "timestamp" column. All other columns are considered values for detecting anomalies. The JSON input file must be of shape `{"data": [{"timestamp": ..., test_value": [value1, value2, ...]}, ...]}`. All timestamp values must be strings in datetime format. The configuration file must specify the following parameters:
   * file_name: The name of the file with the data, located in data/consumer/ directory. (example: "sin.csv")\
The following parameters are similar to ones in Kafka consumer:
   * bootstrap_servers: Kafka server. (example: ["localhost:9092"])
   * auto_offset_reset: (example: "latest")
   * enable_auto_commit": (example: "True")
   * group_id: (example "my-group")
   * value_deserializer": (example "lambda x: loads(x.decode('utf-8'))")
   * topics: A list of topics streaming the data. (example ["anomaly_detection"])

### Output
Output component differs in where the data is outputted to. more than one output conmonent can be specified. It recieves three arguments from the anomaly detection component: value (the last value of the stream), timestamp and status (wether data is anomalous).
1. **Terminal output:** Timestamp, value and status are outputed to the terminal. It does not require any parameters in the configuration file.

2. **Kafka output:** Value is outputed to separate kafka topic. The outputted object is of form: `{"algorithm": [algorithm used], "value": [value of stream in question], "status": [gives information of anomalouesness], "status_code": [gives information of anomalouesness], "timestep": [timestep of the value in stream]}`. Status codes are defined in a following way: OK: 1, warning: 0, error: -1, undefined: 2. It requires the following argments in the config file:
    * output_topic: Name of the topic where the data will be stored (example: "anomaly_detection_EMA")

3. **File output:** Data is outputed to a JSON csv or txt file. The JSON file contains a single field "data" whose value is an array of objects of shape: `{"algorithm": [algorithm used], "value": [value of stream in question], "status": [gives information of anomalouesness], "status_code": [gives information of anomalouesness], "timestep": [timestep of the value in stream]}`. The output in the txt file is the same as terminal output. Status codes are defined in a following way: OK: 1, warning: 0, error: -1, undefined: 2. It requires the following arguments in the config file:
   * file_name: The name of the file for output located in the log/ directory. (example: "output.csv")
   * mode: Wether we want to overwrite the file or just append data to it. (example: "a")

### Visualization
An optional conponent intendet to visualize the inputted stream. 
1. **Graph visualization:** The data is represented as points on graph. All anomaly detection component plot the test_value values and some plot additional values like running average, standard deviation... It requires the following arguments in the config file:
   * num_of_points: Maximum number of points of the same line that are visible on the graph at the same time. (example: 50)
   * num_of_lines: Number of lines plotted on the graph. (TODO: it depends on the anomaly detection algorithm so in future this component will be removed) (example: 4)
   * linestyles: A list, specifying the styles of the lines plotted. (example: ["wo", "r-", "b--", "b--"])

2. **Histogram visualization:** It visualizes the quantity of values, from test_value stream. It requires the following arguments in the config file:
   * num_of_bins: Number of bins in the histogram's range. (example: 50)
   * range: The interval shown on the histogram. (example: [0, 10])
   
3. **Status Points Visualization:** Used to visualize processed data e.g. outputs of EMA or Filtering. The points are colored white if OK, warning yellow, error red or undefined blue.It requires the following arguments in the config file:
   * num_of_points: Maximum number of points of the same line that are visible on the graph at the same time. (example: 50)
   * num_of_lines: Number of lines plotted on the graph. (TODO: it depends on the anomaly detection algorithm so in future this component will be removed) (example: 4)
   * linestyles: A list, specifying the styles of the lines plotted. (example: ["wo", "r-", "b--", "b--"])


### Anomaly detection
The component that does the actual anomaly detection. It recieves data from a consumer component and sends output to output components. The following arguments are general for all conponents:
* input_vector_size: An integer representing the dimensionality of the inputted vector (number of features) (example: 2),
* averages: Specifies additional features to be constructed. In this case averages of the last i values of a feature are calculated and included in the feature vector. (example: [[2, 3, 5], [2]] -> this means that the first feature gets addtitonal features: average over last 2 values, average over last 3 values and average over last 5 values and the second feature gets average over last 2 values)
* shifts: Specifies additional features to be constructed. In this case shifted values of a feature are included in the feature vector. (example: [[1, 2, 3], [4, 5]] -> this means that the first feature gets addtitonal features: value shifted for 1, value shifted for 2 and value shifted for 3 and the second feature gets value shifted for 4 and value shifted for 5)
* "time_features": Specifies additional features to be constructed. In this case the following features can be constructed: day of month, month of year, weekday, hour of day. Note that construction of these features requires datetime format of timestamp. If that is not hte case pass an empty array as parameter for that field. (example: ["day", "month", "weekday", "hour"]),
1. **Border check:** A simple component that checks if the test_value falls within the specified interval and also gives warnings if it is close to the border. It requires the following arguments in the config file:
   * warning_stages: A list of floats from interval [0, 1] which represent different stages of warnings (values above 1 are over the border). (example: [0.7, 0.9])
   * UL: Upper limit of the specified interval. (example: 4)
   * LL: Lower limit of the specified interval. (example: 2)

2. **EMA:** Calculates the exponential moving average of test values. It recieves data from a consumer component and sends output to output components. 
EMA is calculated using past EMA values and the newest test value, giving more weigth to newer data. It is calculated in the following way:
EMA_latest = test_value x smoothing + EMA_last x (1 - smoothing). Warnings are issued if the EMA approaches UL or LL.\
It requires the following arguments in the config file:
   * N: Parameter from which the smoothing is calculated - roughly translates to how many latest test values contribute to the EMA (example: 5)
   * warning_stages: similar to border check - levels to identify EMA approaching limits (example: [0.7, 0.9])
   
3. **Isolation Forest:** iForest algorythm. The basic principle is that an anomalous datapoint is easier to separate from others, than a normal datapoint. In the current implementation, one instance consists of N consecutive (or non-consecutive) test values. Instances are constructed via the "shifts" module. The algorythm can also be modified by adding other features. A pre-trained model can be loaded from the "models" folder, or a new model can be trained with the appropriate train data. Arguments in config file when we're training a new model:
   * train_data: Location of the train data. (example: "data/Continental/0.txt") Data should be in csv format, as it is in the example file. This is an optional parameter. If it is not provided load_model_from must be. 
   * max_features: The number of features to draw from X to train each base estimator. (example: 4)
   * max_samples: The number of samples to draw from X to train each base estimator. (example:100)
   * contamination: The proportion of outliers in the dataset. (example: 0.1 if we know we have 10% of outliers in our dataset) Can be set to "auto".
   * model_name: Name of the model, which will be saved in "models/" folder.
   * retrain_interval: An integer representing the number of samples recieved by the anomaly detection component that trigger model retraining (example: 100)
   * samples_for_retrain": An integer representing the number of most recent samples that are used to retrain the model. If it is not specified it uses all samples (may cause memory overflow). If training dataset is specified those samples are also considered for retraining untill they are overwritten by newer samples. (example: 2000),
Example model train config: IsolationForestTrain.json
Model train mode is activated if "load_model_from" is not in the config file, and "train_data" is defined. After training, the trained model will be used to continue with evaluation of data from consumer automatically.
If we have a pre-trained model, we load it by specifying:
   * load_model_from: location of pre-trained iForest model. This is an optional parameter. If it is not provided train_data must be.  (example: "models/IsolationForest")
in the config file. Example config: IsolationForest.json

4. **PCA:** Principal component analysis. Projects high dimensional data to a lower dimensional space. Very effective first step, if we have a large number of features in an instance (even > 1000). Could be effective to combine PCA followed by e.g. Isolation Forest (TODO)

5. **Welfords algorithm:** Very simmilar to border check only in this case UL and LL are calculated with every new sample (with equations: UL=online_mean_consumption+X*online_standard_+deviation and LL=online_mean_consumption-X*online_standard_+deviation). There are two modes for this method. Frist one calculates mean and standard deviation of the previous N samples and the second one calculates them for all the datasamples so far.
It requires the following arguments in the config file:
   * N: An integer representing the number of samples used for calculating mean and standard deviation. If it is not specified all samples till some point will be used in calculation. (example: 5)
   * warning_stages: A list of floats from interval [0, 1] which represent different stages of warnings (values above 1 are over the border). (example: [0.7, 0.9])
   * X: A parameter in the equation for calculating LL and UL. The larger it is the bigger the interval of normal values it (more false negatives) (example: 1.5)
   
6. **Filtering:** Digital filtering is applied to the input data via a lowpass filter, smoothing the signal. The filter used is Butterworth of the order specified in config. This helps to identify trend changes in the data. Similarly to Border check and EMA, warnings are issued if the filtered signal approaches UL or LL.

The filtered signal helps to identify trend shifts. (mode 0)
Taking the difference between the actual value of each new data point from the current filtered signal value can help to identify sudden spikes. (mode 1) In mode 1 a normalised value is calculated: value = last change in value/(UL-LL). The normalised value is classified according to warning stages or marked as an error id the value is >1 or <-1. 

It requires the following arguments in the config file:
   * UL: Upper limit of the specified interval. (example: 4)
   * LL: Lower limit of the specified interval. (example: 2)
   * warning_stages: similar to e.g. EMA (example: [0.7, 0.9])
   * filter_order: order of the filter - how many latest points are used in the filter response. Most of the time, somewhere around order 3 is enough, as a higher order filter will cause a delay in the filtered signal compared to the real-time data. (example: 3)
   * cutoff_frequency: the frequency, at which the filter response starts to drop off. Lower frequency components of the input data will be passed through, but higher frequency components are filtered out. This is not an actual physical frequency but rather a float between 0 and 1. (example: 0.1)
   * mode: either 0 or 1; 0 - output is the filtered signal, 1 - output is the difference between the test value and the filtered signal (this is for visualization purposes)


## Examples:
For configuration examples see configuration folder and inside it READEME file. <br> <br>
For example with Braila data run `python main.py -f -c braila/"configuration_file_name"`. The results will appear in log directory and can be analized with braila_data.ipynb notebook in notebooks directory.
