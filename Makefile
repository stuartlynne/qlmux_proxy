
# vim: noexpandtab tabstop=8 shiftwidth=8



all:
	@echo "make sdist | install | bdist"

clean:
	rm -f */*pyc
	rm -rf build dist qlmux.egg-info

.PHONY: sdist install bdist


bdist:
	python setup.py $@
sdist:
	python setup.py $@
install:
	python setup.py $@
#install-support:
#	cp -vr bin/* /usr/local/bin

