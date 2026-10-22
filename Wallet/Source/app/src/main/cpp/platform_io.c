#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <signal.h>
#include <sys/prctl.h>

/* renameat2's libc wrapper is API30; the kernel syscall exists on API26.
 * Return errno explicitly so ctypes cannot lose it across the FFI boundary.
 * Failure never falls back to a replacing rename or partial destination copy.
 */
int sumuww_publish_no_replace(const char *source, const char *destination) {
    return syscall(SYS_renameat2, AT_FDCWD, source, AT_FDCWD, destination, 1) == 0
        ? 0 : errno;
}

/* No Python or Java callbacks run between fork and exec. Parent-thread death
 * terminates the helper even when Android stops the host unexpectedly. */
int sumuww_router_spawn(const char *executable, char *const arguments[]) {
    pid_t parent = getpid();
    pid_t child = fork();
    if (child != 0) return (int)child;
    if (prctl(PR_SET_PDEATHSIG, SIGTERM) != 0 || getppid() != parent) _exit(127);
    int nullfd = open("/dev/null", O_RDWR);
    if (nullfd < 0) _exit(127);
    dup2(nullfd, STDIN_FILENO); dup2(nullfd, STDOUT_FILENO); dup2(nullfd, STDERR_FILENO);
    for (int fd = 3; fd < 4096; ++fd) close(fd);
    execv(executable, arguments);
    _exit(127);
}
