import time
import pandas as pd
import sys
from data_updater.trading_utils import get_clob_client
from data_updater.google_utils import get_spreadsheet
from data_updater.find_markets import get_sel_df, get_all_markets, get_all_results, get_markets, add_volatility_to_df
from gspread_dataframe import set_with_dataframe, get_as_dataframe
import traceback

# Initialize global variables
spreadsheet = get_spreadsheet()
client = get_clob_client()

wk_all = spreadsheet.worksheet("All Markets")
wk_vol = spreadsheet.worksheet("Volatility Markets")

sel_df = get_sel_df(spreadsheet, "Selected Markets")

# Global variable to track last spreadsheet update time
last_spreadsheet_update = None

def update_sheet(data, worksheet):
    all_values = worksheet.get_all_values()
    existing_num_rows = len(all_values)
    existing_num_cols = len(all_values[0]) if all_values else 0

    num_rows, num_cols = data.shape
    max_rows = max(num_rows, existing_num_rows)
    max_cols = max(num_cols, existing_num_cols)

    # Create a DataFrame with the maximum size and fill it with empty strings
    padded_data = pd.DataFrame('', index=range(max_rows), columns=range(max_cols))

    # Update the padded DataFrame with the original data and its columns
    padded_data.iloc[:num_rows, :num_cols] = data.values
    padded_data.columns = list(data.columns) + [''] * (max_cols - num_cols)

    # Update the sheet with the padded DataFrame, including column headers
    set_with_dataframe(worksheet, padded_data, include_index=False, include_column_header=True, resize=True)

def sort_df(df):
    # Calculate the mean and standard deviation for each column
    mean_gm = df['gm_reward_per_100'].mean()
    std_gm = df['gm_reward_per_100'].std()
    
    mean_volatility = df['volatility_sum'].mean()
    std_volatility = df['volatility_sum'].std()
    
    # Standardize the columns
    df['std_gm_reward_per_100'] = (df['gm_reward_per_100'] - mean_gm) / std_gm
    df['std_volatility_sum'] = (df['volatility_sum'] - mean_volatility) / std_volatility
    
    # Define a custom scoring function for best_bid and best_ask
    def proximity_score(value):
        if 0.1 <= value <= 0.25:
            return (0.25 - value) / 0.15
        elif 0.75 <= value <= 0.9:
            return (value - 0.75) / 0.15
        else:
            return 0
    
    df['bid_score'] = df['best_bid'].apply(proximity_score)
    df['ask_score'] = df['best_ask'].apply(proximity_score)
    
    # Create a composite score (higher is better for rewards, lower is better for volatility, with proximity scores)
    df['composite_score'] = (
        df['std_gm_reward_per_100'] - 
        df['std_volatility_sum'] + 
        df['bid_score'] + 
        df['ask_score']
    )
    
    # Sort by the composite score in descending order
    sorted_df = df.sort_values(by='composite_score', ascending=False)
    
    # Drop the intermediate columns used for calculation
    sorted_df = sorted_df.drop(columns=['std_gm_reward_per_100', 'std_volatility_sum', 'bid_score', 'ask_score', 'composite_score'])
    
    return sorted_df

def save_market_quality_data(market_quality_df):
    """
    Save market quality data to the 'Markets Quality' worksheet.
    Only updates if more than 1 minute has passed since the last spreadsheet update globally.
    
    Args:
        market_quality_df (pd.DataFrame): DataFrame containing market quality analysis results
    """
    global last_spreadsheet_update
    
    try:
        # Check global timing constraint - must be at least 1 minute since last spreadsheet update
        current_time = pd.Timestamp.now()
        if last_spreadsheet_update is not None:
            time_since_last_global_update = current_time - last_spreadsheet_update
            if time_since_last_global_update.total_seconds() < 60:  # 60 seconds = 1 minute
                # print(f"Skipping market quality update - only {time_since_last_global_update.total_seconds():.0f} seconds since last spreadsheet update")
                return
        
        # Get the spreadsheet instance
        spreadsheet = get_spreadsheet()
        
        # Get or create the 'Markets Quality' worksheet
        try:
            wk_quality = spreadsheet.worksheet("Markets Quality")
        except:
            # Create the worksheet if it doesn't exist
            wk_quality = spreadsheet.add_worksheet(title="Markets Quality", rows=1000, cols=50)
        
        # Get existing data from the worksheet
        try:
            existing_df = get_as_dataframe(wk_quality)
            # Remove empty rows
            existing_df = existing_df.dropna(how='all')
        except:
            # If worksheet is empty, create an empty DataFrame
            existing_df = pd.DataFrame()
        
        # Clean invalid float values before saving
        market_quality_df = market_quality_df.replace([float('inf'), float('-inf')], None)
        market_quality_df = market_quality_df.fillna('')
        
        # Extract the question from market_quality_df
        question = market_quality_df['question'].iloc[0]
        
        # Check if a row with this question already exists
        if not existing_df.empty and 'question' in existing_df.columns:
            # Find existing row with the same question
            existing_row_idx = existing_df[existing_df['question'] == question].index
            
            if len(existing_row_idx) > 0:
                # Update existing row
                for col in market_quality_df.columns:
                    if col in existing_df.columns:
                        existing_df.loc[existing_row_idx[0], col] = market_quality_df[col].iloc[0]
                    else:
                        # Add new column if it doesn't exist
                        existing_df[col] = ''
                        existing_df.loc[existing_row_idx[0], col] = market_quality_df[col].iloc[0]
                
                # Add timestamp
                existing_df.loc[existing_row_idx[0], 'last_updated'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            else:
                # Add new row for new questions
                new_row = market_quality_df.copy()
                new_row['last_updated'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                existing_df = pd.concat([existing_df, new_row], ignore_index=True)
        else:
            # If no existing data, use the new data
            existing_df = market_quality_df.copy()
            existing_df['last_updated'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Clean the final DataFrame before updating sheet
        existing_df = existing_df.replace([float('inf'), float('-inf')], None)
        existing_df = existing_df.fillna('')
        
        # Update the worksheet
        update_sheet(existing_df, wk_quality)
        # Update the global timestamp
        last_spreadsheet_update = current_time
        print(f"Market quality data saved for question: {question}")
        
        # Also update the Selected Markets quality field
        _update_selected_markets_quality(market_quality_df)
        
    except Exception as e:
        print(f"Error saving market quality data: {str(e)}")
        traceback.print_exc()

def _update_selected_markets_quality(market_quality_df):
    """
    Update the quality field in the 'Selected Markets' worksheet for the corresponding question.
    
    Args:
        market_quality_df (pd.DataFrame): DataFrame containing market quality analysis results
    """
    global last_spreadsheet_update
    
    try:
        # Check global timing constraint - must be at least 1 minute since last spreadsheet update
        # current_time = pd.Timestamp.now()
        # if last_spreadsheet_update is not None:
        #     time_since_last_global_update = current_time - last_spreadsheet_update
        #     if time_since_last_global_update.total_seconds() < 60:  # 60 seconds = 1 minute
        #         # print(f"Skipping selected markets quality update - only {time_since_last_global_update.total_seconds():.0f} seconds since last spreadsheet update")
        #         return
        
        # Extract the question and quality score from market_quality_df
        question = market_quality_df['question'].iloc[0]
        quality_score = market_quality_df.get('score', pd.Series([None])).iloc[0]
        
        # Handle invalid quality scores
        if pd.isna(quality_score) or quality_score in [float('inf'), float('-inf')]:
            quality_score = ''
        
        # Get the spreadsheet instance
        spreadsheet = get_spreadsheet()
        
        # Get the 'Selected Markets' worksheet
        try:
            wk_selected = spreadsheet.worksheet("Selected Markets")
        except:
            print(f"Selected Markets worksheet not found, skipping quality update for: {question}")
            return
        
        # Get existing data from the worksheet
        try:
            selected_df = get_as_dataframe(wk_selected)
            # Remove empty rows
            selected_df = selected_df.dropna(how='all')
        except:
            print(f"Error reading Selected Markets worksheet, skipping quality update for: {question}")
            return
        
        # Check if question column exists
        if 'question' not in selected_df.columns:
            print(f"Question column not found in Selected Markets worksheet")
            return
        
        # Find matching question row
        matching_rows = selected_df[selected_df['question'] == question]
        
        if matching_rows.empty:
            # Question not found in Selected Markets, skip silently
            return
        
        # Update quality field for the first matching row
        row_index = matching_rows.index[0]
        
        # Ensure quality column exists
        if 'quality' not in selected_df.columns:
            selected_df['quality'] = ''
        
        # Update the quality value
        selected_df.loc[row_index, 'quality'] = quality_score
        
        # Clean the DataFrame before updating sheet
        selected_df = selected_df.replace([float('inf'), float('-inf')], None)
        selected_df = selected_df.fillna('')
        
        # Update the worksheet
        update_sheet(selected_df, wk_selected)
        
    except Exception as e:
        print(f"Error updating Selected Markets quality: {str(e)}")
        traceback.print_exc()

def fetch_and_process_data(ONLY_SELECTED_MARKETS):
    global spreadsheet, client, wk_all, wk_vol, sel_df
    
    spreadsheet = get_spreadsheet()
    client = get_clob_client()

    wk_all = spreadsheet.worksheet("All Markets")
    wk_vol = spreadsheet.worksheet("Volatility Markets")
    wk_full = spreadsheet.worksheet("Full Markets")

    sel_df = get_sel_df(spreadsheet, "Selected Markets")


    all_df = get_all_markets(client)
    
    if ONLY_SELECTED_MARKETS and len(sel_df) > 0:
        # Filter all_df to only include markets that match selected markets
        selected_questions = sel_df['question'].tolist()
        filtered_df = all_df[all_df['question'].isin(selected_questions)]
        print(f'{pd.to_datetime("now")}: Filtered from {len(all_df)} to {len(filtered_df)} markets based on selected markets.')
        all_results = get_all_results(filtered_df, client)
    else:
        # Keep current behavior - process all markets
        all_results = get_all_results(all_df, client)

    m_data, all_markets = get_markets(all_results, sel_df, maker_reward=0.75)

    print(f'{pd.to_datetime("now")}: Fetched all markets data of length {len(all_markets)}.')
    new_df = add_volatility_to_df(all_markets)
    new_df['volatility_sum'] =  new_df['24_hour'] + new_df['7_day'] + new_df['14_day']
    
    new_df = new_df.sort_values('volatility_sum', ascending=True)
    new_df['volatilty/reward'] = ((new_df['gm_reward_per_100'] / new_df['volatility_sum']).round(2)).astype(str)

    new_df = new_df[['question', 'answer1', 'answer2', 'spread', 'rewards_daily_rate', 'gm_reward_per_100', 'sm_reward_per_100', 'bid_reward_per_100', 'ask_reward_per_100',  'volatility_sum', 'volatilty/reward', 'min_size', '1_hour', '3_hour', '6_hour', '12_hour', '24_hour', '7_day', '30_day',  
                     'best_bid', 'best_ask', 'volatility_price', 'max_spread', 'tick_size',  
                     'neg_risk',  'market_slug', 'token1', 'token2', 'condition_id']]

    
    volatility_df = new_df.copy()
    volatility_df = volatility_df[new_df['volatility_sum'] < 20]
    # volatility_df = sort_df(volatility_df)
    volatility_df = volatility_df.sort_values('gm_reward_per_100', ascending=False)
   
    new_df = new_df.sort_values('gm_reward_per_100', ascending=False)

    print(f'{pd.to_datetime("now")}: Fetched select market of length {len(new_df)}.')

    if len(new_df) > 50 or ONLY_SELECTED_MARKETS:
        update_sheet(new_df, wk_all)
        update_sheet(volatility_df, wk_vol)
        update_sheet(m_data, wk_full)
    else:
        print(f'{pd.to_datetime("now")}: Not updating sheet because of length {len(new_df)}.')

if __name__ == "__main__":
    # Parse command line arguments
    ONLY_SELECTED_MARKETS = True  # Default value
    if len(sys.argv) > 1:
        ONLY_SELECTED_MARKETS = sys.argv[1].lower() in ['true', '1', 'yes', 'on']
    
    while True:
        try:
            fetch_and_process_data(ONLY_SELECTED_MARKETS)
            time.sleep(60 * 5)  # Sleep for 5 minutes (300 seconds)
        except Exception as e:
            traceback.print_exc()
            print(str(e))
