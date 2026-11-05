# Host unit tests for the protocol code: `make -C firmware/fob/tests` (needs cc; gcov for coverage).
CFLAGS = -std=c11 -Wall -Wextra -Werror -O0 -g --coverage

test: test_protocol
	./test_protocol

test_protocol: test_protocol.c ../src/protocol.c ../src/protocol.h
	$(CC) $(CFLAGS) -o $@ test_protocol.c ../src/protocol.c

coverage: test
	gcov -o . test_protocol-protocol.gcda ../src/protocol.c 2>/dev/null || gcov ../src/protocol.c

clean:
	rm -f test_protocol *.gcda *.gcno *.gcov

.PHONY: test coverage clean
