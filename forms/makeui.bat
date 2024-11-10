@echo off
@REM call "C:\OSGeo4W\bin\o4w_env.bat"
@REM call "C:\OSGeo4W\bin\qt5_env.bat"
@REM call "C:\OSGeo4W\bin\py3_env.bat"
rem pyrcc5 -o resources.py resources.qrc
rem pyuic5 -x %%i -o ui_%%~ni.py
@echo on
rem pyuic5 -o resources.py resources.qrc
for %%i in (*.ui) do (
	python -m PyQt5.uic.pyuic -x %%i -o %%~ni.py

)
pause 