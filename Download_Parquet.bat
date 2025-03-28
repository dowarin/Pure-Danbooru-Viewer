@echo off
setlocal enabledelayedexpansion

if not exist "parquet" ( mkdir "parquet" )
curl -o parquet\Dan_post.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Dan_post.parquet
curl -o parquet\Dan_rels.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Dan_rels.parquet
curl -o parquet\Dan_tags.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Dan_tags.parquet
curl -o parquet\Gel_post.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Gel_post.parquet
curl -o parquet\Gel_rels.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Gel_rels.parquet
curl -o parquet\Gel_tags.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/Gel_tags.parquet
curl -o parquet\tarIndex_alphachannel.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/tarIndex_alphachannel.parquet
curl -o parquet\tarIndex_duplicate.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/tarIndex_duplicate.parquet
curl -o parquet\tarIndex_image.parquet -L https://huggingface.co/datasets/dowarin/Pure-Danbooru-Viewer-Parquet/resolve/main/tarIndex_image.parquet
