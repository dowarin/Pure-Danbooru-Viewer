@echo off
setlocal enabledelayedexpansion

if not exist "parquet" ( mkdir "parquet" )
curl -oparquet\Dan_post.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Dan_post.parquet
curl -oparquet\Dan_rels.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Dan_rels.parquet
curl -oparquet\Dan_tags.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Dan_tags.parquet
curl -oparquet\Gel_post.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Gel_post.parquet
curl -oparquet\Gel_rels.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Gel_rels.parquet
curl -oparquet\Gel_tags.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Gel_tags.parquet
curl -oparquet\tarIndex_alphachannel.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/tarIndex_alphachannel.parquet
curl -oparquet\tarIndex_duplicate.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/tarIndex_duplicate.parquet
curl -oparquet\tarIndex_image.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/tarIndex_image.parquet