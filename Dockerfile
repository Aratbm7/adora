# Dockerfile

# Use the official Python image as a base image
FROM python:3.11.4-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
# ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED 1
# ENV PYTHONUNBUFFERED=1

# Set the working directory

ENV HOME=/home/app
ENV APP_HOME=/home/app/backend
RUN mkdir -p $HOME $APP_HOME $APP_HOME/media $APP_HOME/core/static

# Install ping
RUN apt-get update && \
    apt-get install -y iputils-ping && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR $APP_HOME


# # Add user for app
# RUN  addgroup app && useradd -r -g app appuser && chown -R appuser:app /code


# Copy the requirements file into the image
# COPY requirements.txt /code/
COPY requirements-dev.txt .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements-dev.txt


# Copy the rest of the project into the image
COPY . .

# # Copy and set permissions for the entrypoint and wait-for-it scripts
# COPY ./docker-entrypoint.sh /home/app/backend/docker-entrypoint.sh
# COPY ./wait-for-it.sh /home/app/backend/wait-for-it.sh



COPY --chown=adora_u:adora_g docker-entrypoint* wait-for-it.sh $APP_HOME/  

RUN chmod +x $APP_HOME/docker-entrypoint* \
            $APP_HOME/wait-for-it.sh  
# Set User
# USER appuser

EXPOSE 8000

# CMD ["./docker-entrypoint.sh"]
ENTRYPOINT [ "./docker-entrypoint.sh" ]
