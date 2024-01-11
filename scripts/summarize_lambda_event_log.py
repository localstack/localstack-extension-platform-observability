#!/usr/bin/env python3
import sys
from typing import TypedDict
import json
import pandas as pd
import argparse

class LambdaLifecycleEvent(TypedDict):
    """
    Event payload as written to <volume>/cache/observability/traces-lambda/ 
    """
    timestamp: float
    event: str
    request_id: str
    lambda_arn: str
    failure_cause: str | None

def summarize(events: list[LambdaLifecycleEvent]):
    df = pd.DataFrame(events)
    # convert timestamps to make them human readable
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    # pivot dataframe to have one line per lambda event invocation
    grouped = df.pivot_table(columns=["event"], index=["request_id", "lambda_arn"], values="timestamp", aggfunc=lambda x: ",".join(x.astype(str)))
    with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.max_colwidth', 150, 'display.expand_frame_repr', False):
        print(grouped)
        

def main():
    parser = argparse.ArgumentParser(
        prog='Summarize lambda event logs',
        description='Print a table of lambda events, and when which event was processed'
    )
    # operation (put, get)
    parser.add_argument("input_file")
    args = parser.parse_args()

    events: list[LambdaLifecycleEvent] = []
    # read the ndjson file
    with open(args.input_file, mode="rt") as f:
        for line in f:
            line = line.strip()
            events.append(json.loads(line))
    
    summarize(events)
    

if __name__ == "__main__":
    main()