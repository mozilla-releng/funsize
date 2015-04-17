DOCKERIO_USERNAME =$(error DOCKERIO_USERNAME should be set)
IMAGE_NAME = funsize-scheduler
FULL_IMAGE_NAME = $(DOCKERIO_USERNAME)/$(IMAGE_NAME)

build:
	docker build -t $(FULL_IMAGE_NAME) .

push:
	docker push $(FULL_IMAGE_NAME)

run:
	docker run -t -i -v ~/tmp/funsize-logs:/home/worker/funsize-logs -v ~/Private:/home/worker/Private:ro $(FULL_IMAGE_NAME) ./node_modules/.bin/babel-node -r funsize.js -c /home/worker/Private/funsizeconfig.js
