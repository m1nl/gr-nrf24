find_package(PkgConfig)

PKG_CHECK_MODULES(PC_GR_NRF24 gnuradio-nrf24)

FIND_PATH(
    GR_NRF24_INCLUDE_DIRS
    NAMES gnuradio/nrf24/api.h
    HINTS $ENV{NRF24_DIR}/include
        ${PC_NRF24_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    GR_NRF24_LIBRARIES
    NAMES gnuradio-nrf24
    HINTS $ENV{NRF24_DIR}/lib
        ${PC_NRF24_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/gnuradio-nrf24Target.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GR_NRF24 DEFAULT_MSG GR_NRF24_LIBRARIES GR_NRF24_INCLUDE_DIRS)
MARK_AS_ADVANCED(GR_NRF24_LIBRARIES GR_NRF24_INCLUDE_DIRS)
