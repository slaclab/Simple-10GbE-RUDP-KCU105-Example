export TARGET_DIRS  = $(PWD)/targets/RoCEv2_1GbeRudpKcu105Examples \
                      $(PWD)/targets/RoCEv2_10GbeRudpKcu105Example \
                      $(PWD)/targets/RoCEv2_Rj45RudpKcu105Example \
                      $(PWD)/targets/Simple1GbeRudpKcu105Example \
                      $(PWD)/targets/Simple10GbeRudpKcu105Example \
                      $(PWD)/targets/SimpleRj45RudpKcu105Example

.PHONY: all build clean

# Default
all: build

# Check variables
test:
	@echo TARGET_DIRS:
	@echo -e "$(foreach ARG,$(TARGET_DIRS),\t$(ARG)\n)"

# Clean all firmware builds
clean:
	for i in $(TARGET_DIRS); do \
      cd $$i; make clean; \
   done

# Build targets
build:
	for i in $(TARGET_DIRS); do \
      echo $$i; cd $$i; make clean; rm -rf images; make; \
   done
