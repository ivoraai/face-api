"""
Create thumbnail images with max 1000x1000 px while maintaining aspect ratio.
Preserves the original directory structure in a 'thumbnails' folder.
"""

import os
from pathlib import Path
from PIL import Image, ImageOps
from typing import List

# Configuration
MAX_SIZE = (1000, 1000)
THUMBNAIL_ROOT = "thumbnails"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}

def is_image_file(filepath: Path) -> bool:
    """Check if file is an image based on extension."""
    return filepath.suffix.lower() in IMAGE_EXTENSIONS

def create_thumbnail(input_path: Path, output_path: Path, max_size: tuple = MAX_SIZE) -> bool:
    """
    Create a thumbnail of an image while maintaining aspect ratio.

    Args:
        input_path: Path to the input image
        output_path: Path where thumbnail should be saved
        max_size: Maximum dimensions (width, height) for the thumbnail

    Returns:
        True if successful, False otherwise
    """
    try:
        with Image.open(input_path) as img:
            # Fix orientation based on EXIF data
            img = ImageOps.exif_transpose(img)

            # Convert RGBA to RGB if necessary (for saving as JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = rgb_img

            # Calculate new size maintaining aspect ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save thumbnail
            img.save(output_path, quality=90, optimize=True)
            return True

    except Exception as e:
        print(f"Error processing {input_path}: {e}")
        return False

def process_images(source_root: str = ".", thumbnail_root: str = THUMBNAIL_ROOT) -> dict:
    """
    Process all images in the source directory and create thumbnails.

    Args:
        source_root: Root directory to search for images
        thumbnail_root: Root directory for thumbnails

    Returns:
        Dictionary with processing statistics
    """
    source_path = Path(source_root).resolve()
    thumbnail_path = Path(thumbnail_root).resolve()

    # Avoid processing thumbnails directory itself
    stats = {
        'total': 0,
        'successful': 0,
        'failed': 0,
        'skipped': 0
    }

    print(f"Searching for images in: {source_path}")
    print(f"Creating thumbnails in: {thumbnail_path}")
    print(f"Max thumbnail size: {MAX_SIZE[0]}x{MAX_SIZE[1]} px\n")

    # Walk through all directories
    for root, dirs, files in os.walk(source_path):
        current_dir = Path(root)

        # Skip thumbnail directory itself
        if thumbnail_path in current_dir.parents or current_dir == thumbnail_path:
            continue

        # Filter directories to skip thumbnail directory
        dirs[:] = [d for d in dirs if (current_dir / d).resolve() != thumbnail_path]

        for file in files:
            input_file = current_dir / file

            if not is_image_file(input_file):
                continue

            stats['total'] += 1

            # Calculate relative path from source root
            try:
                relative_path = input_file.relative_to(source_path)
            except ValueError:
                # File is not relative to source path, skip
                stats['skipped'] += 1
                continue

            # Create output path maintaining directory structure
            output_file = thumbnail_path / relative_path

            # Check if thumbnail already exists
            if output_file.exists():
                print(f"Skipped (already exists): {relative_path}")
                stats['skipped'] += 1
                continue

            # Create thumbnail
            print(f"Processing: {relative_path}")
            if create_thumbnail(input_file, output_file):
                stats['successful'] += 1
                print(f"  ✓ Created: {output_file}")
            else:
                stats['failed'] += 1
                print(f"  ✗ Failed: {relative_path}")

    return stats

def main():
    """Main function to run the thumbnail generator."""
    print("=" * 60)
    print("Thumbnail Generator")
    print("=" * 60)
    print()

    stats = process_images()

    print()
    print("=" * 60)
    print("Processing Complete!")
    print("=" * 60)
    print(f"Total images found: {stats['total']}")
    print(f"Successfully processed: {stats['successful']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped: {stats['skipped']}")
    print()

if __name__ == "__main__":
    main()
