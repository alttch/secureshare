VERSION=0.0.21

all:
	@echo "Select target"

ver:
	find . -type f -name "*.py" -exec \
			sed -i "s/^__version__ = .*/__version__ = '${VERSION}'/g" {} \;
	find ./bin -type f -exec sed -i "s/^__version__ = .*/__version__ = '${VERSION}'/g" {} \;
	sed -i "s/secureshare==.*/secureshare==${VERSION}/" Dockerfile

clean:
	rm -rf dist build secureshare.egg-info

d: clean sdist

sdist:
	python3 setup.py sdist

build: clean build-packages

build-packages:
	python3 setup.py build

pub:
	jks build secureshare

pub-pypi:
	twine upload dist/*

docker-build:
	docker build -t altertech/secureshare:${VERSION}-${BUILD_NUMBER} .
	docker tag altertech/secureshare:${VERSION}-${BUILD_NUMBER} altertech/secureshare:latest

docker-pub:
	docker push altertech/secureshare:${VERSION}-${BUILD_NUMBER}
	docker push altertech/secureshare:latest
