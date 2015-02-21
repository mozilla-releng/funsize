DOCKER_PREFIX =$(error DOCKER_PREFIX should be set)
IMAGE_NAME = funsize-update-generator
FULL_IMAGE_NAME = $(DOCKER_PREFIX)/$(IMAGE_NAME)

build:
	docker build -t $(FULL_IMAGE_NAME) .

push:
	docker push $(FULL_IMAGE_NAME)
