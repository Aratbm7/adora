# FROM python:3.11.9-slim-buster

# # Set environment variables
# ENV PYTHONDONTWRITEBYTECODE=1 \
#     PYTHONUNBUFFERED=1 \
#     HOME=/home/app \
#     APP_HOME=/home/app/

# # Install ping
# RUN apt-get update && \
#     apt-get install -y iputils-ping && \
#     apt-get clean && \
#     rm -rf /var/lib/apt/lists/*

# WORKDIR $APP_HOME


# # # Add user for app
# # RUN  addgroup app && useradd -r -g app appuser && chown -R appuser:app /code


# # Copy the requirements file into the image
# # COPY requirements.txt /code/
# COPY requirements-dev.txt .

# # Install dependencies
# RUN pip install --upgrade pip
# RUN pip install -r requirements-dev.txt


# # Copy the rest of the project into the image
# COPY . .

# # # Copy and set permissions for the entrypoint and wait-for-it scripts
# # COPY ./docker-entrypoint.sh /home/app/backend/docker-entrypoint.sh
# # COPY ./wait-for-it.sh /home/app/backend/wait-for-it.sh



# COPY --chown=adora_u:adora_g docker-entrypoint* wait-for-it.sh $APP_HOME/

# RUN chmod +x $APP_HOME/docker-entrypoint* \
#             $APP_HOME/wait-for-it.sh
# # Set User
# # USER appuser

# EXPOSE 8000

# # CMD ["./docker-entrypoint.sh"]
# ENTRYPOINT [ "./docker-entrypoint.sh" ]
# FROM python:3.11.9-slim-buster
FROM python:3.11.9-slim-bookworm


# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app \
    APP_HOME=/home/app/

# Install system dependencies
RUN apt-get update && \
    apt-get install -y iputils-ping && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create app user and group
RUN groupadd -r app && \
    useradd -r -g app -d /home/app -s /bin/bash appuser && \
    mkdir -p /home/app && \
    chown -R appuser:app /home/app

# Set working directory
WORKDIR $APP_HOME

# Copy requirements file and install dependencies
COPY requirements-dev.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-dev.txt

# Copy application files
COPY --chown=appuser:app . .

# Copy and set permissions for scripts
COPY --chown=appuser:app docker-entrypoint*.sh wait-for-it.sh $APP_HOME/
RUN chmod +x $APP_HOME/docker-entrypoint*.sh $APP_HOME/wait-for-it.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]
