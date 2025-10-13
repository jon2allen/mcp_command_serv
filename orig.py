l
async def change_dir(
    c_dir : str
) -> str:
   """
   Change the directory to specified string
   relative and absolute paths are supported

   If error - will return string "error: invalid directory"

   """
   logger.info("Received change_dir requst:  '%s'", c_dir )
   try:
      os.chdir( c_dir )
      return( c_dir )
   except:
      logger.info("invalid dir:  '%s'", c_dir )
      return("error: invalid directo
