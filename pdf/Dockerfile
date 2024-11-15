FROM python:3.13-alpine

# Install pandoc
RUN apk add --no-cache pandoc

# Install Flask
RUN pip install flask werkzeug

# Create working directory
WORKDIR /app

# Copy the application code
COPY app.py /app/

# Expose the port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
