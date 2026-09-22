shopt -s dotglob nullglob

for d in */; do

    sub=$(find "$d" -mindepth 1 -maxdepth 1 -type d)

    mv "$sub"/* "$d"

    rmdir "$sub"

done
 