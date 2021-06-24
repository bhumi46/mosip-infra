import sys
import os
from pyspark import SparkContext
from pyspark.streaming import StreamingContext
from pyspark.rdd import RDD
from pyspark.streaming import DStream
from pyspark.streaming.kafka import KafkaUtils
from pyspark.streaming.dstream import TransformedDStream
from pyspark.streaming.util import TransformFunction
from datetime import datetime
from elasticsearch import Elasticsearch

import pprint, StringIO
import json
import datetime

if __name__ == "__main__":
    sc = SparkContext(appName="KafkaStreamFromPostgresDB")
    ssc = StreamingContext(sc, 2)

    # Connection to elastic search - Configure for details
    eshost = "elasticsearch-master.cattle-logging-system"
    esuser = "elastic"
    espassword = "elastic"
    esport = "9200"
    indexname = "master-template"
    es = Elasticsearch(eshost, http_auth=(esuser, espassword), port=esport)
    p=es.ping()
    print(p)
    
    # Connection to Kafka using Direct streaming methods.
    brokers, topic = "kafka:9092", "postgres.master.template" # Advertised listener for Brokers and Topic name
    kStream = KafkaUtils.createDirectStream(ssc, [topic], {"metadata.broker.list" : brokers, "auto.offset.reset" : "smallest"})
    dbRecord = kStream.map(lambda x: x[1])
    dbRecord.map(lambda x: json.loads(x[1]))
    dbRecord.pprint()
    print(dbRecord)

    def sendRecord(rdd):
        list_elements = rdd.collect()
        print("list elements", list_elements)
        # Process record list
        for element in list_elements:
            # Convert string to python dictionary
            record = json.loads(element)
            print("record json", record)

            # Extract the id for unique key for elasticsearch index - configure w.r.t table
            docId = record['payload']['after']['id']
            print("docId", docId)

            # record['date'] = convertEpochDate(record['cr_dtimes']) # example for processing date
            # creation_date = convertEpochDateTime(record['payload']['after']['cr_dtimes']) # example for processing timestamp

            #record['payload']['after']['cr_dtimes'] = creation_date # re-assign processed value

            # Creating elasticsearch index for this record
            res = es.index(index = indexname, id=docId, body=record)
            print("result of index creation")
            print(res['result'])
            es.indices.refresh(index = indexname)

    print("calling SendRecord")
    dbRecord.foreachRDD(sendRecord)

    def convertEpochDateTime(epochDateTime):
        if epochDateTime is not None:
            dtimes_str = str(epochDateTime)
            dtimes_upd = dtimes_str[0:-6]
            sDateTime = datetime.datetime.fromtimestamp(int(dtimes_upd)).strftime('%Y-%m-%dT%H:%M:%S.000Z')                              
            return sDateTime
        else:
            return None

    def convertEpochDate(epochDate):
        if epochDate is not None:
            dtimes_str = str(epochDate)
            dtimes_upd = dtimes_str[0:-6]
            sDate = datetime.datetime.fromtimestamp(int(dtimes_upd)).strftime('%Y-%m-%d')
            return sDate
        else:
            return None

    ssc.start()
    ssc.awaitTermination()
