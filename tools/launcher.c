#define _GNU_SOURCE
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* payload.o from ld -r -b binary payload.tgz */
extern const char _binary_payload_tgz_start[];
extern const char _binary_payload_tgz_end[];

static const char *VERSION = "1.0.0";

static int exists(const char *p) {
    struct stat st;
    return stat(p, &st) == 0;
}

static void mkpath(const char *dir) {
    char tmp[1024];
    snprintf(tmp, sizeof(tmp), "%s", dir);
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = 0;
            mkdir(tmp, 0755);
            *p = '/';
        }
    }
    mkdir(tmp, 0755);
}

int main(int argc, char **argv, char **envp) {
    const char *home = getenv("HOME");
    if (!home) home = "/tmp";
    char root[512], stamp[576], tgz[576];
    snprintf(root, sizeof(root), "%s/.czarne_wilki_prawdy/runtime", home);
    snprintf(stamp, sizeof(stamp), "%s/.version", root);
    snprintf(tgz, sizeof(tgz), "%s/payload.tgz", root);
    mkpath(root);

    int need = 1;
    if (exists(stamp) && exists(root)) {
        FILE *f = fopen(stamp, "r");
        char buf[64] = {0};
        if (f) {
            if (fgets(buf, sizeof(buf), f) && strncmp(buf, VERSION, strlen(VERSION)) == 0)
                need = 0;
            fclose(f);
        }
    }
    if (need) {
        FILE *o = fopen(tgz, "wb");
        if (!o) {
            perror("payload");
            return 1;
        }
        size_t n = (size_t)(_binary_payload_tgz_end - _binary_payload_tgz_start);
        if (fwrite(_binary_payload_tgz_start, 1, n, o) != n) {
            perror("write");
            return 1;
        }
        fclose(o);
        char cmd[1024];
        snprintf(cmd, sizeof(cmd), "tar -xzf '%s' -C '%s'", tgz, root);
        int rc = system(cmd);
        if (rc != 0) {
            fprintf(stderr, "Czarne Wilki Prawdy: nie moge rozpakowac runtime (tar).\n");
            return 1;
        }
        FILE *s = fopen(stamp, "w");
        if (s) {
            fprintf(s, "%s\n", VERSION);
            fclose(s);
        }
        unlink(tgz);
    }

    char py[640], assets[640], wolf[640];
    snprintf(py, sizeof(py), "%s/py", root);
    snprintf(assets, sizeof(assets), "%s/assets", root);
    snprintf(wolf, sizeof(wolf), "%s/wolf.py", root);

    setenv("PYTHONPATH", py, 1);
    setenv("WOLF_ASSETS", assets, 1);
    setenv("PYGAME_HIDE_SUPPORT_PROMPT", "1", 1);

    char *args[4];
    args[0] = "python3";
    args[1] = wolf;
    args[2] = NULL;
    execvp("python3", args);
    perror("python3");
    fprintf(stderr, "Potrzebny systemowy python3 (3.11+).\n");
    return 127;
}
