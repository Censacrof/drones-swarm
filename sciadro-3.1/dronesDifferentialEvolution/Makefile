JC=javac
JFLAGS:=-cp "lib/*:$(NETLOGO_HOME)/app/*"
SRC_DIR=./src
CLASS_DIR=./class

# all files under SRC_DIR that end with .java
SRC_FILES:=$(shell find $(SRC_DIR) -name "*.java")

# substitute: SRC_DIR -> CLASS_DIR; .java -> .class
CLASS_FILES:=$(patsubst $(SRC_DIR)/%, $(CLASS_DIR)/%, $(SRC_FILES:.java=.class))

.PHONY: all
all: SimulationServer

.PHONY: SimulationServer
SimulationServer: SimulationServer.jar

# generate jar
SimulationServer.jar: $(CLASS_FILES)
	cd $(CLASS_DIR) && jar cvf $@ * && cd - && mv $(CLASS_DIR)/$@ .

# compile each .java in SRC_DIR file and put the resulting .class file under CLASS_DIR
$(CLASS_DIR)/%.class: $(SRC_DIR)/%.java
	@mkdir -p $(dir $@)
	$(JC) $(JFLAGS) -d $(CLASS_DIR) $<

.PHONY: clean 
clean:
	rm -rf $(CLASS_DIR)
	rm -f SimulationServer.jar