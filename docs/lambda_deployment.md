# Lambda Deployment Documentation

## Overview
Two Lambda functions handle automated orchestration for the ISMAP pipeline

Function: trigger_glue
File: lambda_functions/trigger_glue.py
Trigger: S3 PUT event on raw/kaggle/*.csv

Function:  extract_holidays_lambda
File: lambda_functions/extract_holidays_lambda.py
Trigger: EventBridge schedule (weekly)

## IAM Role
Both function sahre a single execution role: 'ismap-lambda-execution-role'.

### Trust Policy
This policy allows WS Lambda to assu ethe role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### Permission Policy
The role needs the following permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:HeadObject"
      ],
      "Resource": "arn:aws:s3:::ismap-data-lake/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## S3 Event Notification
- **Bucket**: `ismap-data-lake`
- **Prefix**: `raw/`
- **Suffix**: `.csv`
- **Event type**: `s3:ObjectCreated:Put`
- **Destination**: `trigger_glue` Lambda function

## Event Bridge Schedule
- **Rule name**: `ismap-holidays-weekly`
- **Schedule**: Every Sunday at 02:00 UTC (`cron(0 2 ? * SUN *)`)
- **Destination**: `extract_holidays_lambda` Lambda function
