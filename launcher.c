#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <libgen.h>
#include <mach-o/dyld.h>

int main(int argc, char *argv[]) {
    char path[1024];
    uint32_t size = sizeof(path);
    if (_NSGetExecutablePath(path, &size) != 0) {
        return 1;
    }
    char *dir = dirname(path);
    char script_path[2048];
    snprintf(script_path, sizeof(script_path), "%s/../Resources/app.py", dir);

    if (access(script_path, F_OK) != 0) {
        snprintf(script_path, sizeof(script_path), "%s/../../../app.py", dir);
    }

    // Ensure LanguageTool background service is active
    system("curl -s -f http://localhost:8081/v2/languages >/dev/null 2>&1 || (brew services start languagetool >/dev/null 2>&1 &)");

    setenv("LC_ALL", "en_US.UTF-8", 1);
    setenv("LANG", "en_US.UTF-8", 1);

    char *python_candidates[] = {
        "/opt/homebrew/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
        "/usr/local/bin/python3",
        "/usr/bin/python3",
        NULL
    };

    char *args[] = { "python3", script_path, NULL };

    for (int i = 0; python_candidates[i] != NULL; i++) {
        if (access(python_candidates[i], X_OK) == 0) {
            args[0] = python_candidates[i];
            execv(python_candidates[i], args);
        }
    }

    // Fallback to system PATH python3
    execvp("python3", args);
    perror("execvp failed");
    return 1;
}
