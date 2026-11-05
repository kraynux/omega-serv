# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Moteur HTTP natif d'omega-serv (plan OMEGA-SERV_PLAN-DETAILLE_MOTEUR_CPP.md, lot 2).
#   cmake -S native/omega-http-core -B native/omega-http-core/build -G Ninja -DCMAKE_BUILD_TYPE=Release
#   cmake --build native/omega-http-core/build && native/omega-http-core/build/omega_tests
# Aucune bibliotheque externe a l'execution (plan Q3) ; doctest (MIT, un fichier) pour les tests seulement.
# PCRE2 (filtre WAF, OMEGA-SERV_PLAN-DETAILLE_WAF_NATIF.md) : liee statiquement si libpcre2-8.a existe, sinon
# dynamiquement ; absente, le moteur se compile sans filtre (toute requete va au processus Python, comme avant).
cmake_minimum_required(VERSION 3.20)
project(omega_http_core VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(OMEGA_SANITIZE "ASan + UBSan (tests)" OFF)
option(OMEGA_STATIC_LIBSTDCXX "libstdc++/libgcc statiques (binaire distribue, plan Q4)" OFF)
option(OMEGA_FUZZ "cibles libFuzzer (clang)" OFF)

set(OMEGA_WARNINGS -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wsign-conversion -Wnull-dereference
    -Wdouble-promotion -Wformat=2 -Wimplicit-fallthrough)
# Durcissement (plan §6)
set(OMEGA_HARDENING -fstack-protector-strong -fstack-clash-protection -D_GLIBCXX_ASSERTIONS
    $<$<NOT:$<CONFIG:Debug>>:-D_FORTIFY_SOURCE=3>)  # FORTIFY exige -O
set(OMEGA_LINK_HARDENING -Wl,-z,relro,-z,now -Wl,-z,noexecstack -pie)

add_library(omega_core STATIC
    src/http_parser.cpp
    src/static_rules.cpp
    src/util.cpp
    src/ip.cpp
    src/text.cpp
    src/config.cpp
    src/engine.cpp
    src/ipc.cpp
    src/control.cpp
    src/tls.cpp
    src/blocklist.cpp
    src/log_writer.cpp
    src/server.cpp
    src/waf_filter.cpp
    src/watch_list.cpp
    src/rate_limiter.cpp
)
target_include_directories(omega_core PUBLIC src)
target_compile_options(omega_core PRIVATE ${OMEGA_WARNINGS} ${OMEGA_HARDENING})

find_package(Threads REQUIRED)
# TLS direct (lot 3b) : la meme OpenSSL que le module ssl de Python (bibliotheque du systeme, liee dynamiquement).
find_package(OpenSSL 3.0 REQUIRED)
target_link_libraries(omega_core PUBLIC Threads::Threads OpenSSL::SSL OpenSSL::Crypto)

find_path(PCRE2_INCLUDE_DIR pcre2.h)
find_library(PCRE2_LIBRARY NAMES libpcre2-8.a pcre2-8)
if(PCRE2_INCLUDE_DIR AND PCRE2_LIBRARY)
    message(STATUS "PCRE2 (filtre WAF) : ${PCRE2_LIBRARY}")
    target_include_directories(omega_core PUBLIC ${PCRE2_INCLUDE_DIR})
    target_compile_definitions(omega_core PUBLIC OMEGA_HAS_PCRE2 PCRE2_CODE_UNIT_WIDTH=8)
    target_link_libraries(omega_core PUBLIC ${PCRE2_LIBRARY})
else()
    message(WARNING "PCRE2 introuvable : moteur compile sans filtre WAF (toute requete inspectee par Python)")
endif()

add_executable(omega-http-core src/main.cpp)
target_link_libraries(omega-http-core PRIVATE omega_core)
target_compile_options(omega-http-core PRIVATE ${OMEGA_WARNINGS} ${OMEGA_HARDENING})
target_link_options(omega-http-core PRIVATE ${OMEGA_LINK_HARDENING})
if(OMEGA_STATIC_LIBSTDCXX)
    target_link_options(omega-http-core PRIVATE -static-libstdc++ -static-libgcc)
endif()

add_executable(omega_tests tests/main.cpp tests/test_http_parser.cpp tests/test_vectors.cpp tests/test_util.cpp tests/test_ipc.cpp tests/test_blocklist.cpp tests/test_waf_filter.cpp tests/test_watch_list.cpp tests/test_rate_limiter.cpp)
target_compile_definitions(omega_tests PRIVATE OMEGA_VECTORS_FILE="${CMAKE_CURRENT_SOURCE_DIR}/tests/vectors/rules.tsv"
    OMEGA_WAF_VECTORS_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/vectors")
target_include_directories(omega_tests PRIVATE third_party/doctest)
target_link_libraries(omega_tests PRIVATE omega_core)

if(OMEGA_SANITIZE)
    foreach(target omega_core omega_tests omega-http-core)
        target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
        target_link_options(${target} PRIVATE -fsanitize=address,undefined)
    endforeach()
endif()

if(OMEGA_FUZZ)
    foreach(fuzzer fuzz_http_parser fuzz_engine fuzz_ipc fuzz_waf_filter)
        add_executable(${fuzzer} tests/${fuzzer}.cpp)
        target_link_libraries(${fuzzer} PRIVATE omega_core)
        target_compile_definitions(${fuzzer} PRIVATE OMEGA_WAF_VECTORS_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/vectors")
        target_compile_options(${fuzzer} PRIVATE -fsanitize=fuzzer,address,undefined)
        target_link_options(${fuzzer} PRIVATE -fsanitize=fuzzer,address,undefined)
    endforeach()
    target_compile_options(omega_core PRIVATE -fsanitize=fuzzer-no-link,address,undefined)
    # tous les consommateurs de la bibliotheque instrumentee (tests, binaire) lient les memes runtimes
    target_link_options(omega_core INTERFACE -fsanitize=fuzzer-no-link,address,undefined)
endif()

enable_testing()
add_test(NAME omega_tests COMMAND omega_tests)
