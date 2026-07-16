cmake_minimum_required(VERSION 3.21)

# ── Fetch or find Google Test ──────────────────────────────────────────────
include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(googletest)

# ── Test executable ──────────────────────────────────────────────────────────
add_executable(quantnexus_engine_tests
  test_order_book.cpp
  test_risk_manager.cpp
  test_order_manager.cpp
)

target_link_libraries(quantnexus_engine_tests
  PRIVATE
    quantnexus_engine_core
    GTest::gtest_main
)
target_include_directories(quantnexus_engine_tests
  PRIVATE ${CMAKE_SOURCE_DIR}/include
)

include(GoogleTest)
gtest_discover_tests(quantnexus_engine_tests)
