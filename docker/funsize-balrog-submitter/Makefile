DOCKERIO_USERNAME =$(error DOCKERIO_USERNAME should be set)
IMAGE_NAME = funsize-balrog-submitter
FULL_IMAGE_NAME = $(DOCKERIO_USERNAME)/$(IMAGE_NAME)

build:
	docker build -t $(FULL_IMAGE_NAME) .

push:
	docker push $(FULL_IMAGE_NAME)
