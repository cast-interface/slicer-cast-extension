#-----------------------------------------------------------------------------
set(MODULE_NAME CastInterface)

set(MODULE_PYTHON_SCRIPTS
  CastInterface.py
  Lib/CastHub.py
  Lib/CastImageDisplayClient.py
  Lib/CastConferenceDialog.py
  Lib/CastResourceServers.py
  Lib/cast_conference.py
  Lib/repo_paths.py
  Lib/__init__.py
  )

slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES Resources
  WITH_GENERIC_TESTS
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  slicer_add_python_unittest(SCRIPT CastInterface.py)
  add_subdirectory(Testing)
endif()

#-----------------------------------------------------------------------------
# Bundle standalone components under the installed module directory.
set(_CAST_MOD_DIR "${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/CastInterface")

set(_CAST_INSTALL_EXCLUDES
  PATTERN "__pycache__" EXCLUDE
  PATTERN "*.pyc" EXCLUDE
  PATTERN "*.pyo" EXCLUDE
  PATTERN "volview-client" EXCLUDE
  PATTERN "vtkjs-worklist-client" EXCLUDE
  PATTERN "cast-worklist-example" EXCLUDE
  PATTERN "OHIF-client" EXCLUDE
  PATTERN "slim" EXCLUDE
  PATTERN "deploy" EXCLUDE
  PATTERN "samples" EXCLUDE
  PATTERN "cast-hub.zip" EXCLUDE
  )

install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/cast_hub/"
        DESTINATION "${_CAST_MOD_DIR}/cast_hub"
        ${_CAST_INSTALL_EXCLUDES}
        )

install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/cast_py_client/"
        DESTINATION "${_CAST_MOD_DIR}/cast_py_client"
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.pyo" EXCLUDE
        )

install(DIRECTORY
        "${CMAKE_CURRENT_SOURCE_DIR}/cast_resource_servers/products"
        "${CMAKE_CURRENT_SOURCE_DIR}/cast_resource_servers/runtime"
        DESTINATION "${_CAST_MOD_DIR}/cast_resource_servers"
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.pyo" EXCLUDE
        )

install(FILES
        "${CMAKE_CURRENT_SOURCE_DIR}/cast_resource_servers/resource_server.py"
        "${CMAKE_CURRENT_SOURCE_DIR}/cast_resource_servers/hub_presets.py"
        DESTINATION "${_CAST_MOD_DIR}/cast_resource_servers"
        )

install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/cast_slicer_image_display/lib"
        DESTINATION "${_CAST_MOD_DIR}/cast_slicer_image_display"
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
        PATTERN "*.pyo" EXCLUDE
        )
