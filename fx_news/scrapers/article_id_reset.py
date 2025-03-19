"""
Script to update existing news articles with article IDs.
Run as: python update_article_ids.py
"""
import os
import logging
import glob
import re
from datetime import datetime
from fx_news.scrapers.article_downloader import extract_article_id_from_url

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_news_with_article_ids(folder="fx_news/scrapers/news/yahoo"):
    """
    Scan all existing article files and add article IDs to them.
    Does NOT rename files - only updates the content.
    
    Args:
        folder: Folder containing article files
        
    Returns:
        Tuple of (updated_count, already_had_id_count, error_count)
    """
    article_files = glob.glob(os.path.join(folder, "article_*.txt"))
    logger.info(f"Found {len(article_files)} article files in {folder}")
    
    updated_count = 0
    already_had_id_count = 0
    error_count = 0
    
    for file_path in article_files:
        try:
            # Read the article content
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check if article already has an ID
            if re.search(r'^Article ID:', content, re.MULTILINE):
                logger.info(f"Article already has ID: {file_path}")
                already_had_id_count += 1
                continue
            
            # Extract source URL
            url_match = re.search(r'^Source: (.+)$', content, re.MULTILINE)
            if not url_match:
                logger.warning(f"No source URL found in {file_path}")
                error_count += 1
                continue
                
            url = url_match.group(1).strip()
            
            # Extract article ID from URL
            article_id = extract_article_id_from_url(url)
            
            if not article_id:
                logger.warning(f"Could not extract article ID from URL: {url}")
                error_count += 1
                continue
            
            # Insert article ID after title
            new_content = re.sub(
                r'(# .+\n\n)',
                f'\\1Article ID: {article_id}\n',
                content
            )
            
            # Write updated content back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            updated_count += 1
            logger.info(f"Added article ID {article_id} to {file_path}")
            
        except Exception as e:
            logger.error(f"Error updating article {file_path}: {str(e)}")
            error_count += 1
    
    return (updated_count, already_had_id_count, error_count)

if __name__ == "__main__":
    start_time = datetime.now()
    logger.info("Starting update of existing articles with article IDs...")
    
    updated, already_had_id, errors = update_news_with_article_ids()
    
    total = updated + already_had_id + errors
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info(f"Article update completed in {duration:.2f} seconds")
    logger.info(f"Total articles: {total}")
    logger.info(f"Updated: {updated}")
    logger.info(f"Already had ID: {already_had_id}")
    logger.info(f"Errors: {errors}")
    
    print(f"\nSummary:")
    print(f"  Updated {updated} articles with article IDs")
    print(f"  Skipped {already_had_id} articles that already had IDs")
    print(f"  Encountered {errors} errors")
    print(f"  Total processing time: {duration:.2f} seconds")