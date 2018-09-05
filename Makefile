



all:
	@echo "make sdist | install | bdist"

clean:
	@echo not implemented

.PHONY: sdist install bdist


bdist:
	python setup.py $@
sdist:
	python setup.py $@
install:
	python setup.py $@
