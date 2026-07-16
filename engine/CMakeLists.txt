cmake_minimum_required(VERSION 3.21)
project(quantnexus_engine VERSION 0.1.0 LANGUAGES CXX)

# ── C++ standard ──────────────────────────────────────────────────────────────
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── Build type defaults ───────────────────────────────────────────────────────
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# ── Compiler flags ────────────────────────────────────────────────────────────
add_compile_options(
  -Wall
  -Wextra
  -Wpedantic
  $<$<CONFIG:Release>:-O3>
  $<$<CONFIG:Release>:-march=native>
  $<$<CONFIG:Debug>:-g>
  $<$<CONFIG:Debug>:-fsanitize=address>
)
add_link_options(
  $<$<CONFIG:Debug>:-fsanitize=address>
)

# ── Dependencies ──────────────────────────────────────────────────────────────

# pybind11 — Python/C++ bridge
# Install via: brew install pybind11  OR  pip install pybind11
find_package(pybind11 QUIET)
if(NOT pybind11_FOUND)
  message(STATUS "pybind11 not found via find_package; trying Python module path")
  execute_process(
    COMMAND python3 -c "import pybind11; print(pybind11.get_cmake_dir())"
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  if(pybind11_DIR)
    find_package(pybind11 REQUIRED PATHS ${pybind11_DIR})
  else()
    message(FATAL_ERROR
      "pybind11 not found. Install with:\n"
      "  brew install pybind11\n"
      "  OR: pip install pybind11")
  endif()
endif()

# ── Source files ──────────────────────────────────────────────────────────────

set(ENGINE_SOURCES
  src/order_book.cpp
  src/order_manager.cpp
  src/risk_manager.cpp
)

# ── Core C++ library (no Python dep) ─────────────────────────────────────────
add_library(quantnexus_engine_core STATIC
  ${ENGINE_SOURCES}
)
target_include_directories(quantnexus_engine_core
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# ── Python extension module (pybind11 bridge) ────────────────────────────────
pybind11_add_module(quantnexus_engine
  src/python_bridge.cpp
)
target_link_libraries(quantnexus_engine PRIVATE quantnexus_engine_core)
target_include_directories(quantnexus_engine
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# ── Unit tests ────────────────────────────────────────────────────────────────
option(BUILD_TESTS "Build unit tests" ON)
if(BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests)
endif()

# ── Install ───────────────────────────────────────────────────────────────────
install(TARGETS quantnexus_engine
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
