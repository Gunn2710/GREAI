CXX ?= c++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Iinclude

SRCS := src/fsrs.cpp src/comfort.cpp src/placement.cpp

.PHONY: test clean

build/test_engine: tests/test_engine.cpp $(SRCS) include/vocab_engine/*.hpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) -o $@ tests/test_engine.cpp $(SRCS)

test: build/test_engine
	./build/test_engine

clean:
	rm -rf build
