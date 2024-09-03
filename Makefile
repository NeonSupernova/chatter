# Define variables
PROJECT_NAME = chatter
IMAGE_NAME = $(PROJECT_NAME):latest
CONTAINER_NAME = $(PROJECT_NAME)_container
DOCKERFILE = Dockerfile

# Build the Docker image
build:
	docker build -t $(IMAGE_NAME) -f $(DOCKERFILE) .

# Run the Docker container
run:
	docker run -d --name $(CONTAINER_NAME) -p 5000:5000 $(IMAGE_NAME)

# Stop the Docker container
stop:
	docker stop $(CONTAINER_NAME) || true
	docker rm $(CONTAINER_NAME) || true

# Rebuild and run the container
rerun: stop build run

# Clean up all Docker artifacts
clean:
	docker rmi $(IMAGE_NAME) || true
	docker rm $(CONTAINER_NAME) || true
	docker image prune -f
	docker container prune -f

# Show logs from the container
logs:
	docker logs -f $(CONTAINER_NAME)

# Attach to the container's shell
shell:
	docker exec -it $(CONTAINER_NAME) /bin/sh

scout:
	docker scout quickview

.PHONY: build run stop rerun clean logs shell scout