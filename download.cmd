@echo off

if not exist models mkdir models

for %%m in (%*) do (
    huggingface-cli.exe download %%m --cache-dir .cache --local-dir models\%%~nm --local-dir-use-symlinks False
)
