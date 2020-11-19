#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>

int main(int argc, char **argv) {
    srand(time(NULL) + getpid());
    int n = rand() % 250 + 5;
    usleep(n * 100000);
    if (argc != 2) {
        fprintf(stderr, "Incorrect number of arguments, got %i\n", argc);
        return 1;
    }
    puts(argv[1]);
    return 0;
}
