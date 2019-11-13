#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int SIZE = 500;

void free_matrix_NO_PERF(double **m) {
    for(int i = 0; i < SIZE; i++) free(m[i]);
    free(m);
}

double **empty_matrix_NO_PERF() {
    double **m = (double **)malloc(SIZE * sizeof(double*));
    for (int i = 0; i < SIZE; i++) m[i] = (double *)malloc(SIZE * sizeof(double));
    return m;
}

double **read_matrix_NO_PERF(char *fn) {
    double **m = empty_matrix_NO_PERF();

    FILE * fp;
    char * line = NULL;
    size_t len = 0;
    ssize_t read;

    fp = fopen(fn, "r");
    if (fp == NULL) {
        printf("file not found :c\n");
        exit(EXIT_FAILURE);
    }

    double a[10][10];
    unsigned int row = 0;
    unsigned int col = 0;
    while ((read = getline(&line, &len, fp)) != -1) {
        char * pch;
        pch = strtok (line, " ");
        col = 0;
        while (pch != NULL)
        {
            m[row][col] = atof(pch);
            pch = strtok (NULL, " ");
            col++;
        }
        row++;
    }


    fclose(fp);
    if (line)
        free(line);

    return m;
}

void print_matrix_NO_PERF(double **M) {
    for (int i = 0; i < SIZE; i++) {
        for (int j = 0; j < SIZE; j++) {
            printf("%f ", M[i][j]);
        }
        printf("\n");
    }
}

double **multiply(double **A, double **B) {
    double **C = empty_matrix_NO_PERF();
    for (int i = 0; i < SIZE; i++) {
        for (int j = 0; j < SIZE; j++) {
            C[i][j] = 0;
            for (int k = 0; k < SIZE; k++) {
                C[i][j] += A[i][k]*B[k][j];
            }
        }
    }
    return C;
}

int main(int argc, char const *argv[]) {
    double **A = read_matrix_NO_PERF("tests/matrix_multiply/A.txt");
    double **B = read_matrix_NO_PERF("tests/matrix_multiply/B.txt");
    double **C = multiply(A, B);

    print_matrix_NO_PERF(C);

    free_matrix_NO_PERF(A);
    free_matrix_NO_PERF(B);
    free_matrix_NO_PERF(C);

    return 0;
}