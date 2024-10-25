# Use the official Python 3.11 image from Docker Hub
FROM python:3.12

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8000 for the Django app
EXPOSE 8000

# Default command for the container
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn zendeskapp.wsgi"]
