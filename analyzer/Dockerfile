# AWS Lambda container image. The base image includes the Lambda Runtime
# Interface Emulator, so the same image runs locally (docker compose) and on AWS.
FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY hakem_analyzer ${LAMBDA_TASK_ROOT}/hakem_analyzer

CMD ["hakem_analyzer.handler.lambda_handler"]
